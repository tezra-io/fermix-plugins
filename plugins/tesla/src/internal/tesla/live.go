package tesla

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/teslamotors/vehicle-command/pkg/account"
	"github.com/teslamotors/vehicle-command/pkg/cache"
	"github.com/teslamotors/vehicle-command/pkg/protocol"
	"github.com/teslamotors/vehicle-command/pkg/vehicle"
)

// maxCachedVehicles bounds the in-memory session cache. Cached session state
// saves a handshake on the next command to the same car; it is never written
// to disk, so it dies with the process.
const maxCachedVehicles = 8

// A LiveOpener connects to a real car. It holds no credential of its own: the
// token file and the key file are read afresh on every Open, so a refreshed
// sign-in or a revoked key takes effect on the very next command.
type LiveOpener struct {
	tokenPath string
	keyPath   string
	userAgent string
	now       func() time.Time
	logf      Logf
	sessions  *cache.SessionCache
}

// NewLiveOpener builds the opener the binary runs with.
func NewLiveOpener(tokenPath, keyPath, userAgent string, now func() time.Time, logf Logf) *LiveOpener {
	if userAgent == "" || now == nil || logf == nil {
		panic("tesla: NewLiveOpener needs a user agent, a clock and a logger")
	}
	return &LiveOpener{
		tokenPath: tokenPath,
		keyPath:   keyPath,
		userAgent: userAgent,
		now:       now,
		logf:      logf,
		sessions:  cache.New(maxCachedVehicles),
	}
}

// Open reads the credentials and returns a connectable vehicle.
func (o *LiveOpener) Open(ctx context.Context, vin string) (Vehicle, error) {
	token, err := LoadToken(o.tokenPath, o.now())
	if err != nil {
		return nil, err
	}
	key, err := LoadSigningKey(o.keyPath)
	if err != nil {
		return nil, err
	}

	// account.New picks the regional Fleet API host out of the token's own
	// `aud` claim (pkg/account/account.go:86-115). Its parse failure quotes
	// the offending token payload verbatim (account.go:126), so its message
	// is never passed on — only the one sentence, with a redacted cause.
	acct, err := account.New(token.AccessToken, o.userAgent)
	if err != nil {
		return nil, refuse(SentenceToken, errors.New(Redact(err.Error())))
	}

	car, err := acct.GetVehicle(ctx, vin, key, o.sessions)
	if err != nil {
		return nil, refuse(Redact(err.Error()), err)
	}
	if car == nil {
		return nil, refuse(SentenceNoResponse, fmt.Errorf("no vehicle for vin ending %s", lastFour(vin)))
	}
	return &sdkVehicle{car: car, sessions: o.sessions, logf: o.logf}, nil
}

// sdkVehicle binds the Vehicle seam to Tesla's own client.
type sdkVehicle struct {
	car      *vehicle.Vehicle
	sessions *cache.SessionCache
	logf     Logf
}

func (s *sdkVehicle) Connect(ctx context.Context) error {
	return s.car.Connect(ctx)
}

func (s *sdkVehicle) StartSession(ctx context.Context, domains []protocol.Domain) error {
	return s.car.StartSession(ctx, domains)
}

// Execute makes the one typed SDK call this command stands for.
func (s *sdkVehicle) Execute(ctx context.Context, cmd *Command, args Args) error {
	return cmd.invoke(ctx, s.car, args)
}

// Disconnect keeps the session state for the next command, then closes the
// connection. Both halves run on every path.
func (s *sdkVehicle) Disconnect() {
	if err := s.car.UpdateCachedSessions(s.sessions); err != nil {
		s.logf("could not keep the session for this car: %s", Redact(err.Error()))
	}
	s.car.Disconnect()
}

// lastFour identifies a car in a log line without writing its whole VIN.
func lastFour(vin string) string {
	if len(vin) < 4 {
		return "????"
	}
	return vin[len(vin)-4:]
}
