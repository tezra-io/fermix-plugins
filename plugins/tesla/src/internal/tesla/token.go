package tesla

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"time"
)

// TokenFileEnv names the environment variable through which the Fermix daemon
// hands this process the path of the token file it owns.
const TokenFileEnv = "FERMIX_PLUGIN_TOKEN_FILE"

// expirySkew is the margin by which a token must outlive the moment of use. A
// token inside this window is treated as expired: the round trip to Tesla can
// outlast it, and a mid-flight expiry is indistinguishable from a revoked
// sign-in.
const expirySkew = 30 * time.Second

// A Token is one read of the daemon-owned token file.
type Token struct {
	AccessToken string
	ExpiresAt   time.Time
	// Region is informational. The Fleet API host this helper talks to is
	// derived by the SDK from the token's own `aud` claim
	// (pkg/account/account.go:86-115), never from this field.
	Region      string
	AuthProfile string
	Generation  int
}

// String hides the access token, so that printing a Token — in a log line, a
// test failure, or a %v deep inside some other value — cannot leak it.
func (t Token) String() string {
	return fmt.Sprintf("Token{access_token:%s expires_at:%s region:%q auth_profile:%q generation:%d}",
		redacted, t.ExpiresAt.Format(time.RFC3339), t.Region, t.AuthProfile, t.Generation)
}

// tokenFile mirrors the on-disk shape the daemon writes. `region` is nullable,
// hence the pointer.
type tokenFile struct {
	AccessToken string  `json:"access_token"`
	ExpiresAt   string  `json:"expires_at"`
	Region      *string `json:"region"`
	AuthProfile string  `json:"auth_profile"`
	Generation  int     `json:"generation"`
}

// LoadToken reads and validates the token file at path, as of now.
//
// It is called afresh on every command: the daemon rewrites this file when it
// refreshes the sign-in, so a cached token is a token that goes stale without
// anything noticing. Every failure is one refusal with one sentence, because
// every one of them has the same correction.
func LoadToken(path string, now time.Time) (Token, error) {
	if path == "" {
		return Token{}, refuse(SentenceToken, errors.New(TokenFileEnv+" is not set"))
	}

	body, err := os.ReadFile(path)
	if err != nil {
		return Token{}, refuse(SentenceToken, fmt.Errorf("reading %s: %w", path, err))
	}

	var parsed tokenFile
	if err := json.Unmarshal(body, &parsed); err != nil {
		return Token{}, refuse(SentenceToken, fmt.Errorf("parsing %s: %w", path, err))
	}
	if parsed.AccessToken == "" {
		return Token{}, refuse(SentenceToken, fmt.Errorf("%s has no access_token", path))
	}
	if parsed.ExpiresAt == "" {
		return Token{}, refuse(SentenceToken, fmt.Errorf("%s has no expires_at", path))
	}

	expiresAt, err := time.Parse(time.RFC3339, parsed.ExpiresAt)
	if err != nil {
		return Token{}, refuse(SentenceToken, fmt.Errorf("%s has an unreadable expires_at", path))
	}
	if !expiresAt.After(now.Add(expirySkew)) {
		return Token{}, refuse(SentenceToken, fmt.Errorf("the sign-in in %s expires at %s", path, expiresAt.Format(time.RFC3339)))
	}

	return Token{
		AccessToken: parsed.AccessToken,
		ExpiresAt:   expiresAt,
		Region:      derefString(parsed.Region),
		AuthProfile: parsed.AuthProfile,
		Generation:  parsed.Generation,
	}, nil
}

func derefString(value *string) string {
	if value == nil {
		return ""
	}
	return *value
}
