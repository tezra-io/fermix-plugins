package tesla_test

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/teslamotors/vehicle-command/pkg/connector/inet"
	"github.com/teslamotors/vehicle-command/pkg/protocol"
	verror "github.com/teslamotors/vehicle-command/pkg/protocol/protobuf/errors"
	"github.com/tezra-io/fermix-plugins/plugins/tesla/src/internal/tesla"
)

// fakeVehicle stands in for the SDK's *vehicle.Vehicle so that the whole
// command path can be exercised without touching Tesla.
type fakeVehicle struct {
	connectErr error
	sessionErr error
	executeErr error

	connects    int
	sessions    int
	executes    int
	disconnects int
	domains     []protocol.Domain
}

func (f *fakeVehicle) Connect(context.Context) error {
	f.connects++
	return f.connectErr
}

func (f *fakeVehicle) StartSession(_ context.Context, domains []protocol.Domain) error {
	f.sessions++
	f.domains = domains
	return f.sessionErr
}

func (f *fakeVehicle) Execute(context.Context, *tesla.Command, tesla.Args) error {
	f.executes++
	return f.executeErr
}

func (f *fakeVehicle) Disconnect() { f.disconnects++ }

type fakeOpener struct {
	vehicle *fakeVehicle
	openErr error
	opens   int
	vin     string
}

func (f *fakeOpener) Open(_ context.Context, vin string) (tesla.Vehicle, error) {
	f.opens++
	f.vin = vin
	if f.openErr != nil {
		return nil, f.openErr
	}
	return f.vehicle, nil
}

func fixedClock() func() time.Time {
	at := time.Date(2026, 9, 13, 12, 34, 56, 0, time.UTC)
	return func() time.Time { return at }
}

func startCharging(t *testing.T) *tesla.Command {
	t.Helper()
	cmd, ok := tesla.Lookup("start_charging")
	if !ok {
		t.Fatal("no start_charging command")
	}
	return cmd
}

func TestRunReportsASuccessfulCommand(t *testing.T) {
	opener := &fakeOpener{vehicle: &fakeVehicle{}}

	result, err := tesla.Run(context.Background(), opener, startCharging(t), tesla.Args{VIN: goodVIN}, fixedClock())
	if err != nil {
		t.Fatalf("Run: %v", err)
	}

	want := tesla.Result{
		Command:      "start_charging",
		VIN:          goodVIN,
		Result:       true,
		Reason:       "",
		DispatchedAt: "2026-09-13T12:34:56Z",
	}
	if result != want {
		t.Errorf("result = %+v, want %+v", result, want)
	}
}

func TestRunSerialisesTheResultInTheAgreedShape(t *testing.T) {
	opener := &fakeOpener{vehicle: &fakeVehicle{}}

	result, err := tesla.Run(context.Background(), opener, startCharging(t), tesla.Args{VIN: goodVIN}, fixedClock())
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	body, err := json.Marshal(result)
	if err != nil {
		t.Fatalf("marshalling result: %v", err)
	}

	want := `{"command":"start_charging","vin":"` + goodVIN + `","result":true,"reason":"","dispatched_at":"2026-09-13T12:34:56Z"}`
	if string(body) != want {
		t.Errorf("result JSON =\n%s\nwant\n%s", body, want)
	}
}

// A vehicle that received and authenticated the command and then refused it is
// a normal answer, not an error: the caller learns what the car said.
func TestRunReportsANominalRefusalAsAResult(t *testing.T) {
	nominal := &protocol.NominalError{Details: protocol.NewError("car could not execute command: is_charging", false, false)}
	opener := &fakeOpener{vehicle: &fakeVehicle{executeErr: nominal}}

	result, err := tesla.Run(context.Background(), opener, startCharging(t), tesla.Args{VIN: goodVIN}, fixedClock())
	if err != nil {
		t.Fatalf("Run returned an error for a nominal refusal: %v", err)
	}
	if result.Result {
		t.Error("result = true, want false for a refused command")
	}
	if !strings.Contains(result.Reason, "is_charging") {
		t.Errorf("reason = %q, want the vehicle's own words", result.Reason)
	}
}

func TestRunReportsAVCSECNominalRefusalAsAResult(t *testing.T) {
	nominal := &protocol.NominalError{Details: &protocol.NominalVCSECError{
		Details: &verror.NominalError{GenericError: verror.GenericError_E_GENERICERROR_CLOSURES_OPEN},
	}}
	cmd, ok := tesla.Lookup("lock_doors")
	if !ok {
		t.Fatal("no lock_doors command")
	}
	opener := &fakeOpener{vehicle: &fakeVehicle{executeErr: nominal}}

	result, err := tesla.Run(context.Background(), opener, cmd, tesla.Args{VIN: goodVIN}, fixedClock())
	if err != nil {
		t.Fatalf("Run returned an error for a nominal refusal: %v", err)
	}
	if result.Result {
		t.Error("result = true, want false")
	}
	if result.Reason == "" {
		t.Error("reason is empty, want the vehicle's own words")
	}
}

func TestRunErrorMapping(t *testing.T) {
	unauthorised := &protocol.NominalError{Details: &protocol.NominalVCSECError{
		Details: &verror.NominalError{GenericError: verror.GenericError_E_GENERICERROR_UNAUTHORIZED},
	}}

	cases := []struct {
		name  string
		fake  *fakeVehicle
		want  string
		exact bool
	}{
		{"asleep on connect", &fakeVehicle{connectErr: inet.ErrVehicleNotAwake}, tesla.SentenceAsleep, true},
		{"asleep on dispatch", &fakeVehicle{executeErr: inet.ErrVehicleNotAwake}, tesla.SentenceAsleep, true},
		{"key not paired", &fakeVehicle{sessionErr: protocol.ErrKeyNotPaired}, tesla.SentenceUnpaired, true},
		{"key not paired on dispatch", &fakeVehicle{executeErr: protocol.ErrKeyNotPaired}, tesla.SentenceUnpaired, true},
		{"no private key", &fakeVehicle{executeErr: protocol.ErrRequiresKey}, tesla.SentenceUnpaired, true},
		{"unauthorised nominal", &fakeVehicle{executeErr: unauthorised}, tesla.SentenceUnpaired, true},
		{"may have succeeded", &fakeVehicle{executeErr: protocol.NewError("timed out waiting for the vehicle", true, false)}, tesla.SentenceUnconfirmed, true},
		{"deadline after dispatch", &fakeVehicle{executeErr: context.DeadlineExceeded}, tesla.SentenceUnconfirmed, true},
		{"deadline before dispatch", &fakeVehicle{sessionErr: context.DeadlineExceeded}, tesla.SentenceNoResponse, true},
		{"unknown SDK error", &fakeVehicle{executeErr: errors.New("vehicle responded with an unrecognized status code")}, "vehicle responded with an unrecognized status code", true},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			opener := &fakeOpener{vehicle: tc.fake}

			_, err := tesla.Run(context.Background(), opener, startCharging(t), tesla.Args{VIN: goodVIN}, fixedClock())
			if err == nil {
				t.Fatal("want a refusal, got nil")
			}
			if got := tesla.Explain(err); got != tc.want {
				t.Errorf("sentence = %q, want %q", got, tc.want)
			}
		})
	}
}

// A failure before the command was sent must never claim it was sent, and a
// failure after it was sent must never claim it was not.
func TestRunNeverClaimsAnUnsentCommandWasSent(t *testing.T) {
	opener := &fakeOpener{vehicle: &fakeVehicle{connectErr: protocol.NewError("connection reset", true, false)}}

	_, err := tesla.Run(context.Background(), opener, startCharging(t), tesla.Args{VIN: goodVIN}, fixedClock())
	if err == nil {
		t.Fatal("want a refusal")
	}
	if got := tesla.Explain(err); got == tesla.SentenceUnconfirmed {
		t.Error("a pre-dispatch failure was reported as possibly delivered")
	}
}

func TestRunDispatchesExactlyOnce(t *testing.T) {
	// A transient, retryable-looking error is the case where an application
	// level retry would be tempting. There must not be one.
	fake := &fakeVehicle{executeErr: protocol.NewError("vehicle busy or finishing wake-up", false, true)}
	opener := &fakeOpener{vehicle: fake}

	if _, err := tesla.Run(context.Background(), opener, startCharging(t), tesla.Args{VIN: goodVIN}, fixedClock()); err == nil {
		t.Fatal("want a refusal")
	}
	if fake.executes != 1 {
		t.Errorf("executes = %d, want exactly 1", fake.executes)
	}
	if opener.opens != 1 {
		t.Errorf("opens = %d, want exactly 1", opener.opens)
	}
}

func TestRunDisconnectsOnEveryPath(t *testing.T) {
	cases := map[string]*fakeVehicle{
		"success":         {},
		"connect failed":  {connectErr: errors.New("connect")},
		"session failed":  {sessionErr: errors.New("session")},
		"dispatch failed": {executeErr: errors.New("dispatch")},
	}

	for name, fake := range cases {
		t.Run(name, func(t *testing.T) {
			opener := &fakeOpener{vehicle: fake}

			_, _ = tesla.Run(context.Background(), opener, startCharging(t), tesla.Args{VIN: goodVIN}, fixedClock())

			if fake.disconnects != 1 {
				t.Errorf("disconnects = %d, want exactly 1", fake.disconnects)
			}
		})
	}
}

func TestRunStartsASessionOnlyOnTheDomainTheCommandNeeds(t *testing.T) {
	for _, cmd := range tesla.Commands() {
		t.Run(cmd.Name, func(t *testing.T) {
			fake := &fakeVehicle{}
			opener := &fakeOpener{vehicle: fake}

			if _, err := tesla.Run(context.Background(), opener, cmd, validArgsFor(cmd.Name), fixedClock()); err != nil {
				t.Fatalf("Run: %v", err)
			}
			if len(fake.domains) != 1 || fake.domains[0] != cmd.Domains[0] {
				t.Errorf("session domains = %v, want %v", fake.domains, cmd.Domains)
			}
		})
	}
}

func TestRunRefusesBadArgumentsBeforeOpeningAConnection(t *testing.T) {
	opener := &fakeOpener{vehicle: &fakeVehicle{}}

	_, err := tesla.Run(context.Background(), opener, startCharging(t), tesla.Args{VIN: "TOO-SHORT"}, fixedClock())
	if err == nil {
		t.Fatal("want a refusal")
	}
	if opener.opens != 0 {
		t.Errorf("opens = %d, want 0: the VIN was never valid", opener.opens)
	}
}

func TestRunSurfacesAnOpenerRefusalUnchanged(t *testing.T) {
	opener := &fakeOpener{openErr: &tesla.Refusal{Sentence: tesla.SentenceToken, Cause: errors.New("token file missing")}}

	_, err := tesla.Run(context.Background(), opener, startCharging(t), tesla.Args{VIN: goodVIN}, fixedClock())
	if err == nil {
		t.Fatal("want a refusal")
	}
	if got := tesla.Explain(err); got != tesla.SentenceToken {
		t.Errorf("sentence = %q, want %q", got, tesla.SentenceToken)
	}
}

func TestRunNeverWakesTheCar(t *testing.T) {
	// The Vehicle seam this package drives has no wake verb at all, so no code
	// path can grow one by accident. Guard the property explicitly.
	var seam any = &fakeVehicle{}
	if _, ok := seam.(interface{ Wakeup(context.Context) error }); ok {
		t.Error("the vehicle seam exposes Wakeup; this helper must never wake a car")
	}
}
