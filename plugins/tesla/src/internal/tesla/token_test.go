package tesla_test

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/tezra-io/fermix-plugins/plugins/tesla/src/internal/tesla"
)

// A token file that is well formed and comfortably in the future.
func writeTokenFile(t *testing.T, body string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "token.json")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatalf("writing fixture: %v", err)
	}
	return path
}

func TestLoadTokenAcceptsAWellFormedFile(t *testing.T) {
	now := time.Date(2026, 9, 13, 12, 0, 0, 0, time.UTC)
	path := writeTokenFile(t, `{
		"access_token": "header.payload.signature",
		"expires_at": "2026-09-13T13:00:00Z",
		"region": "eu",
		"auth_profile": "tesla:primary",
		"generation": 4
	}`)

	token, err := tesla.LoadToken(path, now)
	if err != nil {
		t.Fatalf("LoadToken: %v", err)
	}
	if token.AccessToken != "header.payload.signature" {
		t.Errorf("AccessToken = %q", token.AccessToken)
	}
	if got, want := token.ExpiresAt, time.Date(2026, 9, 13, 13, 0, 0, 0, time.UTC); !got.Equal(want) {
		t.Errorf("ExpiresAt = %v, want %v", got, want)
	}
	if token.Region != "eu" || token.AuthProfile != "tesla:primary" || token.Generation != 4 {
		t.Errorf("metadata = %+v", token)
	}
}

func TestLoadTokenAcceptsANullRegion(t *testing.T) {
	now := time.Date(2026, 9, 13, 12, 0, 0, 0, time.UTC)
	path := writeTokenFile(t, `{"access_token":"a.b.c","expires_at":"2026-09-13T13:00:00Z","region":null,"auth_profile":"tesla:primary","generation":1}`)

	token, err := tesla.LoadToken(path, now)
	if err != nil {
		t.Fatalf("LoadToken: %v", err)
	}
	if token.Region != "" {
		t.Errorf("Region = %q, want empty", token.Region)
	}
}

func TestLoadTokenRefusals(t *testing.T) {
	now := time.Date(2026, 9, 13, 12, 0, 0, 0, time.UTC)
	missing := filepath.Join(t.TempDir(), "absent.json")

	cases := []struct {
		name string
		path string
	}{
		{"no path configured", ""},
		{"file missing", missing},
		{"not json", writeTokenFile(t, "not json at all")},
		{"empty access token", writeTokenFile(t, `{"access_token":"","expires_at":"2026-09-13T13:00:00Z"}`)},
		{"missing expires_at", writeTokenFile(t, `{"access_token":"a.b.c"}`)},
		{"unparsable expires_at", writeTokenFile(t, `{"access_token":"a.b.c","expires_at":"tomorrow"}`)},
		{"already expired", writeTokenFile(t, `{"access_token":"a.b.c","expires_at":"2026-09-13T11:00:00Z"}`)},
		{"expires inside the 30s skew window", writeTokenFile(t, `{"access_token":"a.b.c","expires_at":"2026-09-13T12:00:29Z"}`)},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := tesla.LoadToken(tc.path, now)
			if err == nil {
				t.Fatal("want a refusal, got nil")
			}
			if got := tesla.Explain(err); got != tesla.SentenceToken {
				t.Errorf("sentence = %q, want %q", got, tesla.SentenceToken)
			}
			var refusal *tesla.Refusal
			if !errors.As(err, &refusal) {
				t.Fatalf("error %v is not a *tesla.Refusal", err)
			}
			if refusal.Cause == nil {
				t.Error("refusal dropped its cause")
			}
		})
	}
}

func TestLoadTokenAcceptsExpiryJustOutsideTheSkewWindow(t *testing.T) {
	now := time.Date(2026, 9, 13, 12, 0, 0, 0, time.UTC)
	path := writeTokenFile(t, `{"access_token":"a.b.c","expires_at":"2026-09-13T12:00:31Z"}`)

	if _, err := tesla.LoadToken(path, now); err != nil {
		t.Fatalf("LoadToken: %v", err)
	}
}

func TestLoadTokenRefusalNeverQuotesTheToken(t *testing.T) {
	now := time.Date(2026, 9, 13, 12, 0, 0, 0, time.UTC)
	secret := "eyJhbGciOiJSUzI1NiJ9.c3VwZXItc2VjcmV0.c2lnbmF0dXJl"
	path := writeTokenFile(t, `{"access_token":"`+secret+`","expires_at":"2026-09-13T11:00:00Z"}`)

	_, err := tesla.LoadToken(path, now)
	if err == nil {
		t.Fatal("want a refusal")
	}
	if contains(err.Error(), secret) || contains(tesla.Redact(err.Error()), secret) {
		t.Errorf("refusal leaked the token: %v", err)
	}
}

func contains(haystack, needle string) bool {
	return len(needle) > 0 && len(haystack) >= len(needle) && indexOf(haystack, needle) >= 0
}

func indexOf(haystack, needle string) int {
	for i := 0; i+len(needle) <= len(haystack); i++ {
		if haystack[i:i+len(needle)] == needle {
			return i
		}
	}
	return -1
}
