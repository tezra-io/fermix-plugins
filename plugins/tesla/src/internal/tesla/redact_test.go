package tesla_test

import (
	"strings"
	"testing"

	"github.com/tezra-io/fermix-plugins/plugins/tesla/src/internal/tesla"
)

func TestRedactRemovesBearerTokens(t *testing.T) {
	jwt := "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
	text := "http error when sending command: Bearer " + jwt

	got := tesla.Redact(text)

	if strings.Contains(got, jwt) {
		t.Errorf("Redact kept the token: %q", got)
	}
	if !strings.Contains(got, "http error when sending command") {
		t.Errorf("Redact discarded the diagnosis: %q", got)
	}
}

func TestRedactRemovesABareJWT(t *testing.T) {
	jwt := "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJmZXJtaXgifQ.c2lnbmF0dXJlLWhlcmU"

	got := tesla.Redact("client provided malformed OAuth token: " + jwt)

	if strings.Contains(got, "eyJzdWIiOiJmZXJtaXgifQ") {
		t.Errorf("Redact kept the payload: %q", got)
	}
}

func TestRedactRemovesPEMBlocks(t *testing.T) {
	pem := "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIBc3\n-----END EC PRIVATE KEY-----"

	got := tesla.Redact("could not parse " + pem)

	if strings.Contains(got, "MHcCAQEEIBc3") {
		t.Errorf("Redact kept key material: %q", got)
	}
	if !strings.Contains(got, "could not parse") {
		t.Errorf("Redact discarded the diagnosis: %q", got)
	}
}

func TestRedactLeavesOrdinaryTextAlone(t *testing.T) {
	text := "vehicle unavailable: vehicle is offline or asleep"

	if got := tesla.Redact(text); got != text {
		t.Errorf("Redact = %q, want %q", got, text)
	}
}

// Tesla's own account.New quotes the offending token's payload when it cannot
// base64-decode it (pkg/account/account.go:120). A bare payload segment is not
// a whole JWT, so it has to be caught on its own.
func TestRedactRemovesABareTokenPayload(t *testing.T) {
	payload := "eyJzdWIiOiJmZXJtaXgiLCJhdWQiOlsiaHR0cHM6Ly9mbGVldC1hcGkucHJkLmV1LnZuLmNsb3VkLnRlc2xhLmNvbSJdfQ"

	got := tesla.Redact("client provided malformed OAuth token: illegal base64 data at input byte 3 (" + payload + ")")

	if strings.Contains(got, payload) {
		t.Errorf("Redact kept the payload: %q", got)
	}
	if !strings.Contains(got, "illegal base64 data") {
		t.Errorf("Redact discarded the diagnosis: %q", got)
	}
}

// The hardening above must not eat the library's own vocabulary.
func TestRedactKeepsLongLibraryIdentifiers(t *testing.T) {
	for _, text := range []string{
		"vcsec could not execute command: E_GENERICERROR_UNAUTHORIZED",
		"cannot send authenticated command before establishing a vehicle session",
		"MESSAGEFAULT_ERROR_INVALID_TOKEN_OR_COUNTER",
		"http error when sending command to https://fleet-api.prd.eu.vn.cloud.tesla.com/api/1/vehicles/5YJ3E1EA7KF000316/signed_command: 408 Request Timeout",
		"vehicle rejected request: your public key has not been paired with the vehicle",
	} {
		if got := tesla.Redact(text); got != text {
			t.Errorf("Redact changed library text:\n got %q\nwant %q", got, text)
		}
	}
}
