package tesla

// This file is the one test inside the package: it holds the command table to
// the typed SDK call each tool stands for. The connection-level fakes in
// run_test.go cannot see that far — to them every command is one Execute — so
// a seat wired to the wrong SDK constant, or a trunk wired to the wrong end of
// the car, would pass every other test in the suite.

import (
	"context"
	"fmt"
	"slices"
	"testing"

	"github.com/teslamotors/vehicle-command/pkg/vehicle"
)

func at[T any](value T) *T { return &value }

const mappingVIN = "5YJ3E1EA7KF000316"

// recordingCar implements carAPI and writes down each call it received, in the
// SDK's own vocabulary.
type recordingCar struct {
	calls []string
}

func (c *recordingCar) record(format string, args ...any) error {
	c.calls = append(c.calls, fmt.Sprintf(format, args...))
	return nil
}

func (c *recordingCar) ChargeStart(context.Context) error { return c.record("ChargeStart()") }

func (c *recordingCar) ChargeStop(context.Context) error { return c.record("ChargeStop()") }

func (c *recordingCar) ChangeChargeLimit(_ context.Context, percent int32) error {
	return c.record("ChangeChargeLimit(%d)", percent)
}

func (c *recordingCar) SetChargingAmps(_ context.Context, amps int32) error {
	return c.record("SetChargingAmps(%d)", amps)
}

func (c *recordingCar) ChargePortOpen(context.Context) error { return c.record("ChargePortOpen()") }

func (c *recordingCar) ChargePortClose(context.Context) error { return c.record("ChargePortClose()") }

func (c *recordingCar) FlashLights(context.Context) error { return c.record("FlashLights()") }

func (c *recordingCar) HonkHorn(context.Context) error { return c.record("HonkHorn()") }

func (c *recordingCar) OpenFrunk(context.Context) error { return c.record("OpenFrunk()") }

func (c *recordingCar) OpenTrunk(context.Context) error { return c.record("OpenTrunk()") }

func (c *recordingCar) VentWindows(context.Context) error { return c.record("VentWindows()") }

func (c *recordingCar) CloseWindows(context.Context) error { return c.record("CloseWindows()") }

func (c *recordingCar) ClimateOn(context.Context) error { return c.record("ClimateOn()") }

func (c *recordingCar) ClimateOff(context.Context) error { return c.record("ClimateOff()") }

func (c *recordingCar) ChangeClimateTemp(_ context.Context, driver, passenger float32) error {
	return c.record("ChangeClimateTemp(%v, %v)", driver, passenger)
}

func (c *recordingCar) SetPreconditioningMax(_ context.Context, enabled, manualOverride bool) error {
	return c.record("SetPreconditioningMax(%t, %t)", enabled, manualOverride)
}

func (c *recordingCar) SetSeatHeater(_ context.Context, levels map[vehicle.SeatPosition]vehicle.Level) error {
	return c.record("SetSeatHeater(%v)", levels)
}

func (c *recordingCar) SetSeatCooler(_ context.Context, level vehicle.Level, seat vehicle.SeatPosition) error {
	return c.record("SetSeatCooler(%d, %d)", level, seat)
}

func (c *recordingCar) AutoSeatAndClimate(_ context.Context, positions []vehicle.SeatPosition, enabled bool) error {
	return c.record("AutoSeatAndClimate(%v, %t)", positions, enabled)
}

func (c *recordingCar) SetSteeringWheelHeater(_ context.Context, enabled bool) error {
	return c.record("SetSteeringWheelHeater(%t)", enabled)
}

func (c *recordingCar) SetVehicleName(_ context.Context, name string) error {
	return c.record("SetVehicleName(%q)", name)
}

func (c *recordingCar) Lock(context.Context) error { return c.record("Lock()") }

func (c *recordingCar) Unlock(context.Context) error { return c.record("Unlock()") }

func (c *recordingCar) SetSentryMode(_ context.Context, state bool) error {
	return c.record("SetSentryMode(%t)", state)
}

// mappingCases is the whole command table written out as the SDK call each
// tool must make. The want column is built from the SDK's own constants, so a
// seat name bound to the wrong position cannot agree with it.
var mappingCases = []struct {
	name string
	tool string
	args Args
	want string
}{
	{"start charging", "start_charging", Args{VIN: mappingVIN}, "ChargeStart()"},
	{"stop charging", "stop_charging", Args{VIN: mappingVIN}, "ChargeStop()"},
	{"charge limit", "set_charge_limit", Args{VIN: mappingVIN, Percent: at(80)}, "ChangeChargeLimit(80)"},
	{"charging amps", "set_charging_amps", Args{VIN: mappingVIN, Amps: at(16)}, "SetChargingAmps(16)"},
	{"open charge port", "open_charge_port", Args{VIN: mappingVIN}, "ChargePortOpen()"},
	{"close charge port", "close_charge_port", Args{VIN: mappingVIN}, "ChargePortClose()"},
	{"start climate", "start_climate", Args{VIN: mappingVIN}, "ClimateOn()"},
	{"stop climate", "stop_climate", Args{VIN: mappingVIN}, "ClimateOff()"},
	{"cabin temperature", "set_cabin_temperature", Args{VIN: mappingVIN, DriverCelsius: at(21.0)}, "ChangeClimateTemp(21, 21)"},
	{"cabin temperature, both sides", "set_cabin_temperature", Args{VIN: mappingVIN, DriverCelsius: at(21.5), PassengerCelsius: at(19.0)}, "ChangeClimateTemp(21.5, 19)"},
	{"preconditioning max", "set_preconditioning_max", Args{VIN: mappingVIN, Enabled: at(true)}, "SetPreconditioningMax(true, false)"},
	{"lock", "lock_doors", Args{VIN: mappingVIN}, "Lock()"},
	{"unlock", "unlock_doors", Args{VIN: mappingVIN}, "Unlock()"},
	{"sentry mode", "set_sentry_mode", Args{VIN: mappingVIN, Enabled: at(false)}, "SetSentryMode(false)"},
	{"flash lights", "flash_lights", Args{VIN: mappingVIN}, "FlashLights()"},
	{"honk horn", "honk_horn", Args{VIN: mappingVIN}, "HonkHorn()"},
	{
		"seat heater",
		"set_seat_heater",
		Args{VIN: mappingVIN, Seat: at("rear_right"), Level: at(3)},
		fmt.Sprintf("SetSeatHeater(%v)", map[vehicle.SeatPosition]vehicle.Level{vehicle.SeatSecondRowRight: vehicle.LevelHigh}),
	},
	{
		"seat heater, off",
		"set_seat_heater",
		Args{VIN: mappingVIN, Seat: at("front_left"), Level: at(0)},
		fmt.Sprintf("SetSeatHeater(%v)", map[vehicle.SeatPosition]vehicle.Level{vehicle.SeatFrontLeft: vehicle.LevelOff}),
	},
	{
		"seat cooler",
		"set_seat_cooler",
		Args{VIN: mappingVIN, Seat: at("front_right"), Level: at(2)},
		fmt.Sprintf("SetSeatCooler(%d, %d)", vehicle.LevelMed, vehicle.SeatFrontRight),
	},
	{
		"auto seat climate",
		"set_auto_seat_climate",
		Args{VIN: mappingVIN, Seat: at("front_left"), Enabled: at(true)},
		fmt.Sprintf("AutoSeatAndClimate(%v, true)", []vehicle.SeatPosition{vehicle.SeatFrontLeft}),
	},
	{"steering wheel heater", "set_steering_wheel_heater", Args{VIN: mappingVIN, Enabled: at(true)}, "SetSteeringWheelHeater(true)"},
	{"front trunk", "actuate_trunk", Args{VIN: mappingVIN, Which: at("front")}, "OpenFrunk()"},
	{"rear trunk", "actuate_trunk", Args{VIN: mappingVIN, Which: at("rear")}, "OpenTrunk()"},
	{"vent windows", "vent_windows", Args{VIN: mappingVIN}, "VentWindows()"},
	{"close windows", "close_windows", Args{VIN: mappingVIN}, "CloseWindows()"},
	{"vehicle name", "set_vehicle_name", Args{VIN: mappingVIN, Name: at("Bluey")}, `SetVehicleName("Bluey")`},
}

func TestEachToolMakesItsOneTypedSDKCall(t *testing.T) {
	for _, tc := range mappingCases {
		t.Run(tc.name, func(t *testing.T) {
			cmd, ok := Lookup(tc.tool)
			if !ok {
				t.Fatalf("no such tool %q", tc.tool)
			}
			if err := cmd.Validate(tc.args); err != nil {
				t.Fatalf("%s rejected its own mapping case: %v", tc.tool, err)
			}

			car := &recordingCar{}
			if err := cmd.invoke(context.Background(), car, tc.args); err != nil {
				t.Fatalf("invoke: %v", err)
			}

			if len(car.calls) != 1 {
				t.Fatalf("calls = %v, want exactly one SDK call", car.calls)
			}
			if car.calls[0] != tc.want {
				t.Errorf("%s called %s, want %s", tc.tool, car.calls[0], tc.want)
			}
		})
	}
}

// A tool with no mapping case is a tool nothing proves the SDK wiring of, so
// let a new one fail this gate rather than ship unchecked.
func TestEveryToolHasAMappingCase(t *testing.T) {
	var covered []string
	for _, tc := range mappingCases {
		if !slices.Contains(covered, tc.tool) {
			covered = append(covered, tc.tool)
		}
	}

	for _, cmd := range Commands() {
		if !slices.Contains(covered, cmd.Name) {
			t.Errorf("%s has no case in mappingCases", cmd.Name)
		}
	}
}

// The nine seat names are the whole point of the seat tools: a name bound to
// the wrong constant heats the wrong seat and nothing else would notice.
func TestEveryAdvertisedSeatNameCarriesItsSDKPosition(t *testing.T) {
	want := map[string]vehicle.SeatPosition{
		"front_left":      vehicle.SeatFrontLeft,
		"front_right":     vehicle.SeatFrontRight,
		"rear_left":       vehicle.SeatSecondRowLeft,
		"rear_center":     vehicle.SeatSecondRowCenter,
		"rear_right":      vehicle.SeatSecondRowRight,
		"rear_left_back":  vehicle.SeatSecondRowLeftBack,
		"rear_right_back": vehicle.SeatSecondRowRightBack,
		"third_row_left":  vehicle.SeatThirdRowLeft,
		"third_row_right": vehicle.SeatThirdRowRight,
	}

	cmd, ok := Lookup("set_seat_heater")
	if !ok {
		t.Fatal("no set_seat_heater command")
	}
	if len(cmd.Schema.Properties["seat"].Enum) != len(want) {
		t.Fatalf("set_seat_heater advertises %v, want %d seats", cmd.Schema.Properties["seat"].Enum, len(want))
	}

	for name, position := range want {
		t.Run(name, func(t *testing.T) {
			car := &recordingCar{}
			args := Args{VIN: mappingVIN, Seat: &name, Level: at(1)}
			if err := cmd.invoke(context.Background(), car, args); err != nil {
				t.Fatalf("invoke: %v", err)
			}

			want := fmt.Sprintf("SetSeatHeater(%v)", map[vehicle.SeatPosition]vehicle.Level{position: vehicle.LevelLow})
			if car.calls[0] != want {
				t.Errorf("%s called %s, want %s", name, car.calls[0], want)
			}
		})
	}
}

// The advertised level is the SDK's own Level: 0 off, 1 low, 2 medium, 3 high
// (pkg/vehicle/climate.go:135-142). SetSeatCooler adds one to reach the
// protobuf's off-by-one enum (climate.go:28), so the same 0..3 is right for
// both tools.
func TestAdvertisedLevelsAreTheSDKLevels(t *testing.T) {
	want := []vehicle.Level{vehicle.LevelOff, vehicle.LevelLow, vehicle.LevelMed, vehicle.LevelHigh}

	for advertised, level := range want {
		if got := levelFor(advertised); got != level {
			t.Errorf("levelFor(%d) = %d, want %d", advertised, got, level)
		}
	}
}
