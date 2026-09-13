package tesla_test

import (
	"slices"
	"testing"

	"github.com/teslamotors/vehicle-command/pkg/protocol"
	"github.com/tezra-io/fermix-plugins/plugins/tesla/src/internal/tesla"
)

func ptr[T any](value T) *T { return &value }

// The exact surface this helper ships. Tool names are advertised unprefixed:
// the Fermix engine registers a plugin-owned MCP server's tools under
// "<plugin>_", so these reach the model as tesla_start_charging and friends.
var shippedTools = []string{
	"start_charging",
	"stop_charging",
	"set_charge_limit",
	"set_charging_amps",
	"open_charge_port",
	"close_charge_port",
	"start_climate",
	"stop_climate",
	"set_cabin_temperature",
	"set_preconditioning_max",
	"lock_doors",
	"unlock_doors",
	"set_sentry_mode",
	"flash_lights",
	"honk_horn",
}

func TestCommandsShipsTheExpectedSurface(t *testing.T) {
	var names []string
	for _, cmd := range tesla.Commands() {
		names = append(names, cmd.Name)
	}

	if !slices.Equal(names, shippedTools) {
		t.Errorf("Commands() = %v\nwant %v", names, shippedTools)
	}
}

// navigate_to is deliberately absent: the SDK has no typed method for it and
// the proxy maps navigation_request to ErrCommandUseRESTAPI
// (pkg/proxy/command.go:509-510), so it cannot be signed end to end.
func TestCommandsDoesNotShipNavigateTo(t *testing.T) {
	if _, ok := tesla.Lookup("navigate_to"); ok {
		t.Error("navigate_to is advertised, but it cannot be signed by the SDK")
	}
}

func TestEveryCommandIsFullyDescribed(t *testing.T) {
	for _, cmd := range tesla.Commands() {
		t.Run(cmd.Name, func(t *testing.T) {
			if cmd.Description == "" {
				t.Error("no description")
			}
			if len(cmd.Domains) != 1 {
				t.Errorf("Domains = %v, want exactly one", cmd.Domains)
			}
			if cmd.Schema == nil {
				t.Fatal("no input schema")
			}
			if cmd.Schema.Type != "object" {
				t.Errorf("schema type = %q, want object", cmd.Schema.Type)
			}
			if _, ok := cmd.Schema.Properties["vin"]; !ok {
				t.Error("schema has no vin property")
			}
			if !slices.Contains(cmd.Schema.Required, "vin") {
				t.Errorf("Required = %v, want it to include vin", cmd.Schema.Required)
			}
		})
	}
}

// Lock and unlock terminate on the vehicle security controller
// (pkg/vehicle/security.go:306-312 -> executeRKEAction -> getVCSECResult,
// pkg/vehicle/vcsec.go:88). Everything else this helper ships goes through
// executeCarServerAction, which targets infotainment
// (pkg/vehicle/infotainment.go:28).
func TestCommandDomainsMatchTheSDKRouting(t *testing.T) {
	vcsecOnly := map[string]bool{"lock_doors": true, "unlock_doors": true}

	for _, cmd := range tesla.Commands() {
		want := protocol.DomainInfotainment
		if vcsecOnly[cmd.Name] {
			want = protocol.DomainVCSEC
		}
		if got := cmd.Domains[0]; got != want {
			t.Errorf("%s domain = %v, want %v", cmd.Name, got, want)
		}
	}
}

const goodVIN = "5YJ3E1EA7KF000316"

func TestValidateRejectsEveryBadVIN(t *testing.T) {
	for _, vin := range []string{"", "5YJ3E1EA7KF00031", "5YJ3E1EA7KF0003166"} {
		for _, cmd := range tesla.Commands() {
			args := validArgsFor(cmd.Name)
			args.VIN = vin

			err := cmd.Validate(args)
			if err == nil {
				t.Fatalf("%s accepted a %d-character VIN", cmd.Name, len(vin))
			}
			if got := tesla.Explain(err); got != tesla.SentenceVIN {
				t.Errorf("%s sentence = %q, want %q", cmd.Name, got, tesla.SentenceVIN)
			}
		}
	}
}

func TestValidateAcceptsEveryWellFormedCall(t *testing.T) {
	for _, cmd := range tesla.Commands() {
		if err := cmd.Validate(validArgsFor(cmd.Name)); err != nil {
			t.Errorf("%s rejected valid arguments: %v", cmd.Name, err)
		}
	}
}

func TestValidateBounds(t *testing.T) {
	cases := []struct {
		name string
		tool string
		args tesla.Args
	}{
		{"charge limit below floor", "set_charge_limit", tesla.Args{VIN: goodVIN, Percent: ptr(49)}},
		{"charge limit above ceiling", "set_charge_limit", tesla.Args{VIN: goodVIN, Percent: ptr(101)}},
		{"charge limit absent", "set_charge_limit", tesla.Args{VIN: goodVIN}},
		{"amps below floor", "set_charging_amps", tesla.Args{VIN: goodVIN, Amps: ptr(0)}},
		{"amps above ceiling", "set_charging_amps", tesla.Args{VIN: goodVIN, Amps: ptr(49)}},
		{"amps absent", "set_charging_amps", tesla.Args{VIN: goodVIN}},
		{"driver temperature below floor", "set_cabin_temperature", tesla.Args{VIN: goodVIN, DriverCelsius: ptr(14.9)}},
		{"driver temperature above ceiling", "set_cabin_temperature", tesla.Args{VIN: goodVIN, DriverCelsius: ptr(28.1)}},
		{"driver temperature absent", "set_cabin_temperature", tesla.Args{VIN: goodVIN}},
		{"passenger temperature out of range", "set_cabin_temperature", tesla.Args{VIN: goodVIN, DriverCelsius: ptr(21.0), PassengerCelsius: ptr(30.0)}},
		{"sentry flag absent", "set_sentry_mode", tesla.Args{VIN: goodVIN}},
		{"preconditioning flag absent", "set_preconditioning_max", tesla.Args{VIN: goodVIN}},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			cmd, ok := tesla.Lookup(tc.tool)
			if !ok {
				t.Fatalf("no such tool %q", tc.tool)
			}
			if err := cmd.Validate(tc.args); err == nil {
				t.Fatalf("%s accepted %+v", tc.tool, tc.args)
			}
		})
	}
}

func TestValidateAcceptsTheBoundsThemselves(t *testing.T) {
	cases := []struct {
		tool string
		args tesla.Args
	}{
		{"set_charge_limit", tesla.Args{VIN: goodVIN, Percent: ptr(50)}},
		{"set_charge_limit", tesla.Args{VIN: goodVIN, Percent: ptr(100)}},
		{"set_charging_amps", tesla.Args{VIN: goodVIN, Amps: ptr(1)}},
		{"set_charging_amps", tesla.Args{VIN: goodVIN, Amps: ptr(48)}},
		{"set_cabin_temperature", tesla.Args{VIN: goodVIN, DriverCelsius: ptr(15.0)}},
		{"set_cabin_temperature", tesla.Args{VIN: goodVIN, DriverCelsius: ptr(28.0)}},
		{"set_cabin_temperature", tesla.Args{VIN: goodVIN, DriverCelsius: ptr(28.0), PassengerCelsius: ptr(15.0)}},
	}

	for _, tc := range cases {
		cmd, ok := tesla.Lookup(tc.tool)
		if !ok {
			t.Fatalf("no such tool %q", tc.tool)
		}
		if err := cmd.Validate(tc.args); err != nil {
			t.Errorf("%s rejected %+v: %v", tc.tool, tc.args, err)
		}
	}
}

// A command that takes no extra argument must not silently accept one: the
// schema forbids it on the wire, and the validator forbids it in process.
func TestValidateRejectsArgumentsTheCommandDoesNotTake(t *testing.T) {
	cmd, ok := tesla.Lookup("start_charging")
	if !ok {
		t.Fatal("no start_charging")
	}

	if err := cmd.Validate(tesla.Args{VIN: goodVIN, Percent: ptr(80)}); err == nil {
		t.Error("start_charging accepted a percent argument")
	}
}

// validArgsFor returns the minimal well-formed argument set for a tool.
func validArgsFor(tool string) tesla.Args {
	args := tesla.Args{VIN: goodVIN}
	switch tool {
	case "set_charge_limit":
		args.Percent = ptr(80)
	case "set_charging_amps":
		args.Amps = ptr(16)
	case "set_cabin_temperature":
		args.DriverCelsius = ptr(21.0)
	case "set_sentry_mode", "set_preconditioning_max":
		args.Enabled = ptr(true)
	}
	return args
}
