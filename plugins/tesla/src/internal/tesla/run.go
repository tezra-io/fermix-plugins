package tesla

import (
	"context"
	"errors"
	"time"

	"github.com/teslamotors/vehicle-command/pkg/connector/inet"
	"github.com/teslamotors/vehicle-command/pkg/protocol"
	verror "github.com/teslamotors/vehicle-command/pkg/protocol/protobuf/errors"
)

// A Vehicle is the slice of Tesla's *vehicle.Vehicle this helper drives. It is
// an interface so the command path can be tested without a car; note that it
// has no wake verb, because this helper must never wake one.
type Vehicle interface {
	Connect(ctx context.Context) error
	StartSession(ctx context.Context, domains []protocol.Domain) error
	Execute(ctx context.Context, cmd *Command, args Args) error
	Disconnect()
}

// An Opener produces a Vehicle for one VIN, having first read the token and
// the signing key.
type Opener interface {
	Open(ctx context.Context, vin string) (Vehicle, error)
}

// A Result is the body of a successful tool call: the command reached the car
// and the car answered, whether it obliged or refused.
type Result struct {
	Command      string `json:"command"`
	VIN          string `json:"vin"`
	Result       bool   `json:"result"`
	Reason       string `json:"reason"`
	DispatchedAt string `json:"dispatched_at"`
}

// Run performs one command against one car.
//
// The command is dispatched exactly once. This package adds no retry of its
// own, and there is no SDK knob to disable the retransmission the SDK does
// internally, so what it does is worth stating: vehicle.Send retries only
// while protocol.ShouldRetry says so (pkg/vehicle/vehicle.go:236-257), and
// ShouldRetry refuses to retry anything whose MayHaveSucceeded is true
// (pkg/protocol/error.go:123-136). A command that might already have reached
// the car is therefore never retransmitted, and the ctx deadline bounds the
// rest.
func Run(ctx context.Context, opener Opener, cmd *Command, args Args, now func() time.Time) (Result, error) {
	if err := cmd.Validate(args); err != nil {
		return Result{}, err
	}

	car, err := opener.Open(ctx, args.VIN)
	if err != nil {
		return Result{}, err
	}
	defer car.Disconnect()

	if err := car.Connect(ctx); err != nil {
		return Result{}, beforeDispatch(err)
	}
	if err := car.StartSession(ctx, cmd.Domains); err != nil {
		return Result{}, beforeDispatch(err)
	}

	dispatchedAt := now().UTC().Format(time.RFC3339)
	return afterDispatch(car.Execute(ctx, cmd, args), cmd, args, dispatchedAt)
}

// beforeDispatch classifies a failure that happened while connecting or
// handshaking. Nothing was sent yet, so no outcome here may suggest the
// command might have run.
func beforeDispatch(err error) error {
	if unpaired(err) {
		return refuse(SentenceUnpaired, err)
	}
	if errors.Is(err, inet.ErrVehicleNotAwake) {
		return refuse(SentenceAsleep, err)
	}
	if timedOut(err) {
		return refuse(SentenceNoResponse, err)
	}
	return refuse(Redact(err.Error()), err)
}

// afterDispatch classifies the outcome of the one typed call.
func afterDispatch(err error, cmd *Command, args Args, dispatchedAt string) (Result, error) {
	answered := Result{Command: cmd.Name, VIN: args.VIN, DispatchedAt: dispatchedAt}

	switch {
	case err == nil:
		answered.Result = true
		return answered, nil
	case unpaired(err):
		return Result{}, refuse(SentenceUnpaired, err)
	case protocol.IsNominalError(err):
		// The car authenticated the command and declined it. That is an
		// answer, and the caller gets the car's own words for it.
		answered.Reason = Redact(err.Error())
		return answered, nil
	case errors.Is(err, inet.ErrVehicleNotAwake):
		return Result{}, refuse(SentenceAsleep, err)
	case protocol.MayHaveSucceeded(err) || timedOut(err):
		// The command went out and nothing came back. Saying it failed would
		// invite a second send of a command that may already have run.
		return Result{}, refuse(SentenceUnconfirmed, err)
	default:
		return Result{}, refuse(Redact(err.Error()), err)
	}
}

// unpaired reports whether err means the application's key is not usable on
// this car: the vehicle rejected the key id, the client had no key at all, or
// the security controller answered with an authorisation fault.
func unpaired(err error) bool {
	if errors.Is(err, protocol.ErrKeyNotPaired) || errors.Is(err, protocol.ErrRequiresKey) {
		return true
	}
	var vcsecErr *protocol.NominalVCSECError
	if !errors.As(err, &vcsecErr) {
		return false
	}
	return vcsecErr.Details.GetGenericError() == verror.GenericError_E_GENERICERROR_UNAUTHORIZED
}

func timedOut(err error) bool {
	return errors.Is(err, context.DeadlineExceeded) || errors.Is(err, context.Canceled)
}
