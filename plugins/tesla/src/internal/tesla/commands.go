package tesla

import (
	"context"
	"fmt"

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
	invoke func(context.Context, *vehicle.Vehicle, Args) error
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
		simple("start_charging", "Start charging the car. The car must be plugged in.", (*vehicle.Vehicle).ChargeStart),
		simple("stop_charging", "Stop the car's current charging session.", (*vehicle.Vehicle).ChargeStop),
		chargeLimit(),
		chargingAmps(),
		simple("open_charge_port", "Open the car's charge port door.", (*vehicle.Vehicle).ChargePortOpen),
		simple("close_charge_port", "Close the car's charge port door.", (*vehicle.Vehicle).ChargePortClose),
		simple("start_climate", "Turn the car's climate control on.", (*vehicle.Vehicle).ClimateOn),
		simple("stop_climate", "Turn the car's climate control off.", (*vehicle.Vehicle).ClimateOff),
		cabinTemperature(),
		preconditioningMax(),
		lockDoors(),
		unlockDoors(),
		sentryMode(),
		simple("flash_lights", "Flash the car's headlights once.", (*vehicle.Vehicle).FlashLights),
		simple("honk_horn", "Sound the car's horn once.", (*vehicle.Vehicle).HonkHorn),
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
func simple(name, description string, call func(*vehicle.Vehicle, context.Context) error) *Command {
	return &Command{
		Name:        name,
		Description: description,
		Domains:     []protocol.Domain{protocol.DomainInfotainment},
		invoke: func(ctx context.Context, car *vehicle.Vehicle, _ Args) error {
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
		invoke: func(ctx context.Context, car *vehicle.Vehicle, args Args) error {
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
		invoke: func(ctx context.Context, car *vehicle.Vehicle, args Args) error {
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
		invoke: func(ctx context.Context, car *vehicle.Vehicle, args Args) error {
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
		invoke: func(ctx context.Context, car *vehicle.Vehicle, args Args) error {
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
		invoke: func(ctx context.Context, car *vehicle.Vehicle, args Args) error {
			return car.SetSentryMode(ctx, *args.Enabled)
		},
	}
}

// Lock and unlock are remote keyless entry actions, which terminate on the
// vehicle security controller (pkg/vehicle/security.go:306-312 ->
// executeRKEAction -> getVCSECResult, pkg/vehicle/vcsec.go:88).
func lockDoors() *Command {
	cmd := simple("lock_doors", "Lock the car's doors.", (*vehicle.Vehicle).Lock)
	cmd.Domains = []protocol.Domain{protocol.DomainVCSEC}
	return cmd
}

func unlockDoors() *Command {
	cmd := simple("unlock_doors", "Unlock the car's doors.", (*vehicle.Vehicle).Unlock)
	cmd.Domains = []protocol.Domain{protocol.DomainVCSEC}
	return cmd
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
