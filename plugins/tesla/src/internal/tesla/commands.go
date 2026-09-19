package tesla

import (
	"context"
	"fmt"
	"slices"
	"strings"
	"unicode"
	"unicode/utf8"

	"github.com/google/jsonschema-go/jsonschema"
	"github.com/teslamotors/vehicle-command/pkg/protocol"
	"github.com/teslamotors/vehicle-command/pkg/vehicle"
)

// The bounds every call is held to. They are declared once and used twice: in
// the JSON schema the model reads, and in the validator the command path runs.
const (
	vinLength      = 17
	minChargeLimit = 50
	maxChargeLimit = 100
	minAmps        = 1
	maxAmps        = 48
	minCelsius     = 15.0
	maxCelsius     = 28.0
	minSeatLevel   = 0
	maxSeatLevel   = 3
	minNameLength  = 1
	maxNameLength  = 32
)

// Args carries every argument any command takes. A pointer field that is nil
// was not supplied; each command accepts exactly the subset it declares and
// refuses the rest.
type Args struct {
	VIN              string   `json:"vin"`
	Percent          *int     `json:"percent,omitempty"`
	Amps             *int     `json:"amps,omitempty"`
	DriverCelsius    *float64 `json:"driver_celsius,omitempty"`
	PassengerCelsius *float64 `json:"passenger_celsius,omitempty"`
	Enabled          *bool    `json:"enabled,omitempty"`
	Seat             *string  `json:"seat,omitempty"`
	Level            *int     `json:"level,omitempty"`
	Which            *string  `json:"which,omitempty"`
	Name             *string  `json:"name,omitempty"`
}

// A Command is one advertised tool: what it is called, what it accepts, which
// vehicle subsystem it terminates on, and the typed SDK call it makes.
type Command struct {
	Name        string
	Description string
	// Domains is the one subsystem StartSession opens. Opening only what the
	// command needs avoids waking infotainment for a VCSEC-only command.
	Domains []protocol.Domain
	Schema  *jsonschema.Schema

	params []param
	check  func(Args) error
	invoke func(context.Context, carAPI, Args) error
}

// Validate refuses a call before anything reaches the network.
func (c *Command) Validate(args Args) error {
	if len(args.VIN) != vinLength {
		return refuse(SentenceVIN, fmt.Errorf("%s got a %d-character vin", c.Name, len(args.VIN)))
	}
	if err := c.rejectUnexpected(args); err != nil {
		return err
	}
	if c.check == nil {
		return nil
	}
	return c.check(args)
}

// rejectUnexpected refuses an argument this command does not declare, so that
// a misaimed value can never be silently ignored.
func (c *Command) rejectUnexpected(args Args) error {
	accepted := make(map[string]bool, len(c.params))
	for _, p := range c.params {
		accepted[p.name] = true
	}
	for _, name := range suppliedNames(args) {
		if !accepted[name] {
			return refuse(fmt.Sprintf(SentenceUnexpectedArgFmt, name), fmt.Errorf("%s does not take %s", c.Name, name))
		}
	}
	return nil
}

// suppliedNames lists the optional arguments present in args.
func suppliedNames(args Args) []string {
	var names []string
	if args.Percent != nil {
		names = append(names, "percent")
	}
	if args.Amps != nil {
		names = append(names, "amps")
	}
	if args.DriverCelsius != nil {
		names = append(names, "driver_celsius")
	}
	if args.PassengerCelsius != nil {
		names = append(names, "passenger_celsius")
	}
	if args.Enabled != nil {
		names = append(names, "enabled")
	}
	if args.Seat != nil {
		names = append(names, "seat")
	}
	if args.Level != nil {
		names = append(names, "level")
	}
	if args.Which != nil {
		names = append(names, "which")
	}
	if args.Name != nil {
		names = append(names, "name")
	}
	return names
}

// Commands returns the tools this helper advertises, in a stable order.
//
// Names are unprefixed on purpose: Fermix registers a plugin-owned MCP
// server's tools under "<plugin>_", so start_charging reaches the model as
// tesla_start_charging.
//
// navigate_to is absent. The SDK has no typed navigation method, and its proxy
// maps navigation_request to ErrCommandUseRESTAPI
// (pkg/proxy/command.go:509-510) because the endpoint needs server-side
// processing that strict end-to-end authentication cannot survive. It ships on
// the plain HTTP rail instead.
func Commands() []*Command {
	commands := []*Command{
		simple("start_charging", "Start charging the car. The car must be plugged in.", carAPI.ChargeStart),
		simple("stop_charging", "Stop the car's current charging session.", carAPI.ChargeStop),
		chargeLimit(),
		chargingAmps(),
		simple("open_charge_port", "Open the car's charge port door.", carAPI.ChargePortOpen),
		simple("close_charge_port", "Close the car's charge port door.", carAPI.ChargePortClose),
		simple("start_climate", "Turn the car's climate control on.", carAPI.ClimateOn),
		simple("stop_climate", "Turn the car's climate control off.", carAPI.ClimateOff),
		cabinTemperature(),
		preconditioningMax(),
		lockDoors(),
		unlockDoors(),
		sentryMode(),
		simple("flash_lights", "Flash the car's headlights once.", carAPI.FlashLights),
		simple("honk_horn", "Sound the car's horn once.", carAPI.HonkHorn),
		seatHeater(),
		seatCooler(),
		autoSeatClimate(),
		steeringWheelHeater(),
		actuateTrunk(),
		simple("vent_windows", "Vent the car's windows, leaving them slightly open.", carAPI.VentWindows),
		simple("close_windows", "Close the car's windows.", carAPI.CloseWindows),
		vehicleName(),
	}
	for _, cmd := range commands {
		cmd.Schema = inputSchema(cmd.params)
	}
	return commands
}

// Lookup returns the command with the given advertised name.
func Lookup(name string) (*Command, bool) {
	for _, cmd := range Commands() {
		if cmd.Name == name {
			return cmd, true
		}
	}
	return nil, false
}

// simple builds a command whose only argument is the VIN and which terminates
// on infotainment, which is where executeCarServerAction routes every action
// (pkg/vehicle/infotainment.go:27).
func simple(name, description string, call func(carAPI, context.Context) error) *Command {
	return &Command{
		Name:        name,
		Description: description,
		Domains:     []protocol.Domain{protocol.DomainInfotainment},
		invoke: func(ctx context.Context, car carAPI, _ Args) error {
			return call(car, ctx)
		},
	}
}

func chargeLimit() *Command {
	return &Command{
		Name:        "set_charge_limit",
		Description: "Set the car's charge limit as a percentage of battery capacity.",
		Domains:     []protocol.Domain{protocol.DomainInfotainment},
		params: []param{{
			name:     "percent",
			required: true,
			schema:   integerSchema(minChargeLimit, maxChargeLimit, "Charge limit as a percentage, 50 to 100."),
		}},
		check: func(args Args) error {
			return requireInt(args.Percent, "percent", minChargeLimit, maxChargeLimit)
		},
		invoke: func(ctx context.Context, car carAPI, args Args) error {
			return car.ChangeChargeLimit(ctx, int32(*args.Percent))
		},
	}
}

func chargingAmps() *Command {
	return &Command{
		Name:        "set_charging_amps",
		Description: "Set the current the car draws while charging, in amps.",
		Domains:     []protocol.Domain{protocol.DomainInfotainment},
		params: []param{{
			name:     "amps",
			required: true,
			schema:   integerSchema(minAmps, maxAmps, "Charging current in amps, 1 to 48."),
		}},
		check: func(args Args) error {
			return requireInt(args.Amps, "amps", minAmps, maxAmps)
		},
		invoke: func(ctx context.Context, car carAPI, args Args) error {
			return car.SetChargingAmps(ctx, int32(*args.Amps))
		},
	}
}

func cabinTemperature() *Command {
	return &Command{
		Name:        "set_cabin_temperature",
		Description: "Set the cabin temperature in degrees Celsius.",
		Domains:     []protocol.Domain{protocol.DomainInfotainment},
		params: []param{
			{
				name:     "driver_celsius",
				required: true,
				schema:   numberSchema(minCelsius, maxCelsius, "Driver-side temperature in degrees Celsius, 15 to 28."),
			},
			{
				name:   "passenger_celsius",
				schema: numberSchema(minCelsius, maxCelsius, "Passenger-side temperature in degrees Celsius, 15 to 28. Defaults to the driver-side value."),
			},
		},
		check: func(args Args) error {
			if err := requireNumber(args.DriverCelsius, "driver_celsius", minCelsius, maxCelsius); err != nil {
				return err
			}
			if args.PassengerCelsius == nil {
				return nil
			}
			return requireNumber(args.PassengerCelsius, "passenger_celsius", minCelsius, maxCelsius)
		},
		invoke: func(ctx context.Context, car carAPI, args Args) error {
			driver := float32(*args.DriverCelsius)
			passenger := driver
			if args.PassengerCelsius != nil {
				passenger = float32(*args.PassengerCelsius)
			}
			return car.ChangeClimateTemp(ctx, driver, passenger)
		},
	}
}

func preconditioningMax() *Command {
	return &Command{
		Name:        "set_preconditioning_max",
		Description: "Turn the car's maximum cabin preconditioning on or off.",
		Domains:     []protocol.Domain{protocol.DomainInfotainment},
		params: []param{{
			name:     "enabled",
			required: true,
			schema:   booleanSchema("true turns maximum preconditioning on, false turns it off."),
		}},
		check: func(args Args) error {
			return requireBool(args.Enabled, "enabled")
		},
		invoke: func(ctx context.Context, car carAPI, args Args) error {
			// The second argument is the manual override, which this helper
			// never asks for (pkg/vehicle/climate.go:194).
			return car.SetPreconditioningMax(ctx, *args.Enabled, false)
		},
	}
}

func sentryMode() *Command {
	return &Command{
		Name:        "set_sentry_mode",
		Description: "Turn the car's sentry mode on or off.",
		Domains:     []protocol.Domain{protocol.DomainInfotainment},
		params: []param{{
			name:     "enabled",
			required: true,
			schema:   booleanSchema("true turns sentry mode on, false turns it off."),
		}},
		check: func(args Args) error {
			return requireBool(args.Enabled, "enabled")
		},
		invoke: func(ctx context.Context, car carAPI, args Args) error {
			return car.SetSentryMode(ctx, *args.Enabled)
		},
	}
}

// Lock and unlock are remote keyless entry actions, which terminate on the
// vehicle security controller (pkg/vehicle/security.go:306-312 ->
// executeRKEAction -> getVCSECResult, pkg/vehicle/vcsec.go:88).
func lockDoors() *Command {
	cmd := simple("lock_doors", "Lock the car's doors.", carAPI.Lock)
	cmd.Domains = []protocol.Domain{protocol.DomainVCSEC}
	return cmd
}

func unlockDoors() *Command {
	cmd := simple("unlock_doors", "Unlock the car's doors.", carAPI.Unlock)
	cmd.Domains = []protocol.Domain{protocol.DomainVCSEC}
	return cmd
}

// Seat heating, seat cooling and steering wheel heating all need the car's
// climate control to be on. When it is not, the car authenticates the command
// and declines it, which afterDispatch already reports as result:false with
// the car's own reason; there is no second rule here.
func seatHeater() *Command {
	names := seatNames(heatableSeats)
	return &Command{
		Name:        "set_seat_heater",
		Description: "Set one seat's heater level. The car's climate control must be on for seat heating to take effect.",
		Domains:     []protocol.Domain{protocol.DomainInfotainment},
		params: []param{
			{
				name:     "seat",
				required: true,
				schema:   enumSchema(names, "Which seat to heat."),
			},
			{
				name:     "level",
				required: true,
				schema:   integerSchema(minSeatLevel, maxSeatLevel, "Heater level: 0 off, 1 low, 2 medium, 3 high."),
			},
		},
		check: func(args Args) error {
			if err := requireEnum(args.Seat, "seat", names); err != nil {
				return err
			}
			return requireInt(args.Level, "level", minSeatLevel, maxSeatLevel)
		},
		invoke: func(ctx context.Context, car carAPI, args Args) error {
			position := seatPosition(heatableSeats, *args.Seat)
			return car.SetSeatHeater(ctx, map[vehicle.SeatPosition]vehicle.Level{position: levelFor(*args.Level)})
		},
	}
}

func seatCooler() *Command {
	names := seatNames(frontSeats)
	return &Command{
		Name:        "set_seat_cooler",
		Description: "Set one front seat's cooling level, on cars with ventilated seats. The car's climate control must be on for seat cooling to take effect.",
		Domains:     []protocol.Domain{protocol.DomainInfotainment},
		params: []param{
			{
				name:     "seat",
				required: true,
				schema:   enumSchema(names, "Which front seat to cool."),
			},
			{
				name:     "level",
				required: true,
				schema:   integerSchema(minSeatLevel, maxSeatLevel, "Cooling level: 0 off, 1 low, 2 medium, 3 high."),
			},
		},
		check: func(args Args) error {
			if err := requireEnum(args.Seat, "seat", names); err != nil {
				return err
			}
			return requireInt(args.Level, "level", minSeatLevel, maxSeatLevel)
		},
		invoke: func(ctx context.Context, car carAPI, args Args) error {
			// SetSeatCooler takes the level first and the seat second
			// (pkg/vehicle/climate.go:11).
			return car.SetSeatCooler(ctx, levelFor(*args.Level), seatPosition(frontSeats, *args.Seat))
		},
	}
}

func autoSeatClimate() *Command {
	names := seatNames(frontSeats)
	return &Command{
		Name:        "set_auto_seat_climate",
		Description: "Turn automatic climate control for one front seat on or off, so the car manages that seat's heating and cooling itself.",
		Domains:     []protocol.Domain{protocol.DomainInfotainment},
		params: []param{
			{
				name:     "seat",
				required: true,
				schema:   enumSchema(names, "Which front seat to manage automatically."),
			},
			{
				name:     "enabled",
				required: true,
				schema:   booleanSchema("true lets the car manage the seat, false leaves it to the seat heater and cooler."),
			},
		},
		check: func(args Args) error {
			if err := requireEnum(args.Seat, "seat", names); err != nil {
				return err
			}
			return requireBool(args.Enabled, "enabled")
		},
		invoke: func(ctx context.Context, car carAPI, args Args) error {
			positions := []vehicle.SeatPosition{seatPosition(frontSeats, *args.Seat)}
			return car.AutoSeatAndClimate(ctx, positions, *args.Enabled)
		},
	}
}

func steeringWheelHeater() *Command {
	return &Command{
		Name:        "set_steering_wheel_heater",
		Description: "Turn the car's steering wheel heater on or off. The car's climate control must be on for it to take effect.",
		Domains:     []protocol.Domain{protocol.DomainInfotainment},
		params: []param{{
			name:     "enabled",
			required: true,
			schema:   booleanSchema("true turns the steering wheel heater on, false turns it off."),
		}},
		check: func(args Args) error {
			return requireBool(args.Enabled, "enabled")
		},
		invoke: func(ctx context.Context, car carAPI, args Args) error {
			return car.SetSteeringWheelHeater(ctx, *args.Enabled)
		},
	}
}

// A trunk is a closure action, which the SDK sends to the vehicle security
// controller rather than to infotainment (pkg/vehicle/actions.go:17,27 ->
// executeClosureAction, pkg/vehicle/vcsec.go:217-249 -> getVCSECResult,
// vcsec.go:88).
func actuateTrunk() *Command {
	ends := []string{"front", "rear"}
	return &Command{
		Name: "actuate_trunk",
		Description: "Open the front trunk, or operate the rear trunk. front opens the frunk, which cannot be closed remotely. " +
			"rear moves the rear trunk: it opens a closed one, and closes an open one on cars with a powered rear trunk.",
		Domains: []protocol.Domain{protocol.DomainVCSEC},
		params: []param{{
			name:     "which",
			required: true,
			schema:   enumSchema(ends, "Which trunk to operate: front for the frunk, rear for the boot."),
		}},
		check: func(args Args) error {
			return requireEnum(args.Which, "which", ends)
		},
		invoke: func(ctx context.Context, car carAPI, args Args) error {
			// The proxy maps the same two words to the same two calls
			// (pkg/proxy/command.go:187-195).
			switch *args.Which {
			case "front":
				return car.OpenFrunk(ctx)
			case "rear":
				return car.OpenTrunk(ctx)
			}
			panic("tesla: actuate_trunk reached an unvalidated trunk: " + *args.Which)
		},
	}
}

func vehicleName() *Command {
	return &Command{
		Name:        "set_vehicle_name",
		Description: "Rename the car. The new name is what the Tesla app and the car's own display show.",
		Domains:     []protocol.Domain{protocol.DomainInfotainment},
		params: []param{{
			name:     "name",
			required: true,
			schema:   stringSchema(minNameLength, maxNameLength, "The car's new name, 1 to 32 characters, with no control characters."),
		}},
		check: func(args Args) error {
			return requireText(args.Name, "name", minNameLength, maxNameLength)
		},
		invoke: func(ctx context.Context, car carAPI, args Args) error {
			return car.SetVehicleName(ctx, *args.Name)
		},
	}
}

func requireInt(value *int, name string, low, high int) error {
	if value == nil {
		return refuse(fmt.Sprintf(SentenceMissingArgFmt, name), fmt.Errorf("%s was not supplied", name))
	}
	if *value < low || *value > high {
		return refuse(fmt.Sprintf(SentenceIntRangeFmt, name, low, high), fmt.Errorf("%s was %d", name, *value))
	}
	return nil
}

func requireNumber(value *float64, name string, low, high float64) error {
	if value == nil {
		return refuse(fmt.Sprintf(SentenceMissingArgFmt, name), fmt.Errorf("%s was not supplied", name))
	}
	if *value < low || *value > high {
		return refuse(fmt.Sprintf(SentenceCelsiusRangeFmt, name, low, high), fmt.Errorf("%s was %g", name, *value))
	}
	return nil
}

func requireBool(value *bool, name string) error {
	if value == nil {
		return refuse(fmt.Sprintf(SentenceMissingArgFmt, name), fmt.Errorf("%s was not supplied", name))
	}
	return nil
}

// requireEnum holds an argument to the exact set the schema advertises, and
// names that set in the refusal so the caller can correct it in one go.
func requireEnum(value *string, name string, allowed []string) error {
	if value == nil {
		return refuse(fmt.Sprintf(SentenceMissingArgFmt, name), fmt.Errorf("%s was not supplied", name))
	}
	if !slices.Contains(allowed, *value) {
		return refuse(fmt.Sprintf(SentenceEnumFmt, name, strings.Join(allowed, ", ")), fmt.Errorf("%s was %q", name, *value))
	}
	return nil
}

// requireText bounds a free-text argument by its length in characters, and
// refuses control characters: the car displays this text, and a caller cannot
// see what a stray newline or escape did to it.
func requireText(value *string, name string, low, high int) error {
	if value == nil {
		return refuse(fmt.Sprintf(SentenceMissingArgFmt, name), fmt.Errorf("%s was not supplied", name))
	}
	if length := utf8.RuneCountInString(*value); length < low || length > high {
		return refuse(fmt.Sprintf(SentenceTextLengthFmt, name, low, high), fmt.Errorf("%s was %d characters", name, length))
	}
	for _, character := range *value {
		if unicode.IsControl(character) {
			return refuse(fmt.Sprintf(SentenceTextControlFmt, name), fmt.Errorf("%s contains %U", name, character))
		}
	}
	return nil
}
