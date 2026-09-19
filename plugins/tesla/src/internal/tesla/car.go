package tesla

import (
	"context"

	"github.com/teslamotors/vehicle-command/pkg/vehicle"
)

// carAPI is the slice of Tesla's *vehicle.Vehicle that the command table
// calls: one typed method per advertised tool and nothing else.
//
// It is an interface for one reason. Which SDK call a tool maps to, and with
// which arguments, is the half of this package that no connection-level fake
// can prove — the seat a caller named must reach SetSeatHeater as the SDK's
// own constant, or the wrong seat warms up. Naming the surface here lets a
// test record the call; *vehicle.Vehicle is the only implementation that
// ships, and the assertion below is what keeps this list honest.
type carAPI interface {
	// pkg/vehicle/charge.go
	ChargeStart(ctx context.Context) error
	ChargeStop(ctx context.Context) error
	ChangeChargeLimit(ctx context.Context, chargeLimitPercent int32) error
	SetChargingAmps(ctx context.Context, amps int32) error

	// pkg/vehicle/actions.go
	ChargePortOpen(ctx context.Context) error
	ChargePortClose(ctx context.Context) error
	FlashLights(ctx context.Context) error
	HonkHorn(ctx context.Context) error
	OpenFrunk(ctx context.Context) error
	OpenTrunk(ctx context.Context) error
	VentWindows(ctx context.Context) error
	CloseWindows(ctx context.Context) error

	// pkg/vehicle/climate.go
	ClimateOn(ctx context.Context) error
	ClimateOff(ctx context.Context) error
	ChangeClimateTemp(ctx context.Context, driverCelsius, passengerCelsius float32) error
	SetPreconditioningMax(ctx context.Context, enabled, manualOverride bool) error
	SetSeatHeater(ctx context.Context, levels map[vehicle.SeatPosition]vehicle.Level) error
	SetSeatCooler(ctx context.Context, level vehicle.Level, seat vehicle.SeatPosition) error
	AutoSeatAndClimate(ctx context.Context, positions []vehicle.SeatPosition, enabled bool) error
	SetSteeringWheelHeater(ctx context.Context, enabled bool) error

	// pkg/vehicle/infotainment.go
	SetVehicleName(ctx context.Context, name string) error

	// pkg/vehicle/security.go
	Lock(ctx context.Context) error
	Unlock(ctx context.Context) error
	SetSentryMode(ctx context.Context, state bool) error
}

// The SDK's own vehicle is the only thing this helper ever drives.
var _ carAPI = (*vehicle.Vehicle)(nil)
