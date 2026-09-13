package tesla_test

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"encoding/pem"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"github.com/tezra-io/fermix-plugins/plugins/tesla/src/internal/tesla"
)

func writeKeyFile(t *testing.T, curve elliptic.Curve, mode os.FileMode) string {
	t.Helper()
	key, err := ecdsa.GenerateKey(curve, rand.Reader)
	if err != nil {
		t.Fatalf("generating key: %v", err)
	}
	der, err := x509.MarshalECPrivateKey(key)
	if err != nil {
		t.Fatalf("marshalling key: %v", err)
	}
	path := filepath.Join(t.TempDir(), "key.pem")
	if err := os.WriteFile(path, pem.EncodeToMemory(&pem.Block{Type: "EC PRIVATE KEY", Bytes: der}), 0o600); err != nil {
		t.Fatalf("writing key: %v", err)
	}
	if err := os.Chmod(path, mode); err != nil {
		t.Fatalf("chmod: %v", err)
	}
	return path
}

func TestLoadSigningKeyAcceptsAPrivateP256Key(t *testing.T) {
	path := writeKeyFile(t, elliptic.P256(), 0o600)

	key, err := tesla.LoadSigningKey(path)
	if err != nil {
		t.Fatalf("LoadSigningKey: %v", err)
	}
	if key == nil {
		t.Fatal("LoadSigningKey returned a nil key with no error")
	}
}

func TestLoadSigningKeyAcceptsAnOwnerOnlyReadableKey(t *testing.T) {
	path := writeKeyFile(t, elliptic.P256(), 0o400)

	if _, err := tesla.LoadSigningKey(path); err != nil {
		t.Fatalf("LoadSigningKey: %v", err)
	}
}

func TestLoadSigningKeyRefusesAnUnsetPath(t *testing.T) {
	_, err := tesla.LoadSigningKey("")
	if err == nil {
		t.Fatal("want a refusal")
	}
	if got := tesla.Explain(err); got != tesla.SentenceKeyUnset {
		t.Errorf("sentence = %q, want %q", got, tesla.SentenceKeyUnset)
	}
}

func TestLoadSigningKeyRefusesAMissingFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "absent.pem")

	_, err := tesla.LoadSigningKey(path)
	if err == nil {
		t.Fatal("want a refusal")
	}
	if got, want := tesla.Explain(err), fmt.Sprintf(tesla.SentenceKeyMissingFmt, path); got != want {
		t.Errorf("sentence = %q, want %q", got, want)
	}
}

func TestLoadSigningKeyRefusesADirectory(t *testing.T) {
	dir := t.TempDir()

	_, err := tesla.LoadSigningKey(dir)
	if err == nil {
		t.Fatal("want a refusal")
	}
	if got, want := tesla.Explain(err), fmt.Sprintf(tesla.SentenceKeyNotRegularFmt, dir); got != want {
		t.Errorf("sentence = %q, want %q", got, want)
	}
}

func TestLoadSigningKeyRefusesGroupOrWorldReadableModes(t *testing.T) {
	for _, mode := range []os.FileMode{0o640, 0o604, 0o660, 0o644, 0o666} {
		t.Run(fmt.Sprintf("mode %o", mode), func(t *testing.T) {
			path := writeKeyFile(t, elliptic.P256(), mode)

			_, err := tesla.LoadSigningKey(path)
			if err == nil {
				t.Fatal("want a refusal")
			}
			want := fmt.Sprintf(tesla.SentenceKeyPermissionsFmt, path, path)
			if got := tesla.Explain(err); got != want {
				t.Errorf("sentence = %q, want %q", got, want)
			}
		})
	}
}

func TestLoadSigningKeyRefusesANonP256Curve(t *testing.T) {
	path := writeKeyFile(t, elliptic.P384(), 0o600)

	_, err := tesla.LoadSigningKey(path)
	if err == nil {
		t.Fatal("want a refusal")
	}
	if got, want := tesla.Explain(err), fmt.Sprintf(tesla.SentenceKeyInvalidFmt, path); got != want {
		t.Errorf("sentence = %q, want %q", got, want)
	}
}

func TestLoadSigningKeyRefusesGarbage(t *testing.T) {
	path := filepath.Join(t.TempDir(), "key.pem")
	if err := os.WriteFile(path, []byte("this is not a PEM block"), 0o600); err != nil {
		t.Fatalf("writing fixture: %v", err)
	}

	_, err := tesla.LoadSigningKey(path)
	if err == nil {
		t.Fatal("want a refusal")
	}
	if got, want := tesla.Explain(err), fmt.Sprintf(tesla.SentenceKeyInvalidFmt, path); got != want {
		t.Errorf("sentence = %q, want %q", got, want)
	}
}

func TestLoadSigningKeyRefusalNeverQuotesKeyMaterial(t *testing.T) {
	path := writeKeyFile(t, elliptic.P384(), 0o600)
	pemBytes, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("reading fixture: %v", err)
	}

	_, loadErr := tesla.LoadSigningKey(path)
	if loadErr == nil {
		t.Fatal("want a refusal")
	}
	body := string(pemBytes)
	for _, text := range []string{loadErr.Error(), tesla.Explain(loadErr), tesla.Redact(fmt.Sprint(loadErr))} {
		if contains(text, body) {
			t.Errorf("refusal leaked key material: %q", text)
		}
	}
}
