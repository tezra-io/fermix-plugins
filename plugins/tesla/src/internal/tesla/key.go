package tesla

import (
	"errors"
	"fmt"
	"io/fs"
	"os"

	"github.com/teslamotors/vehicle-command/pkg/protocol"
)

// SigningKeyEnv names the environment variable holding the path of the PEM
// file with the application's prime256v1 private key.
const SigningKeyEnv = "SIGNING_KEY_PATH"

// sharedModeBits are the group and other permission bits. A signing key that
// any of them are set on is a key another account on this machine can read,
// and therefore a key that can unlock the owner's car.
const sharedModeBits = fs.FileMode(0o077)

// LoadSigningKey checks and loads the signing key at path.
//
// Like the token, this runs on every command rather than once at startup: the
// guarantee worth having is that the key was sound and private at the moment
// it signed, not at the moment the process booted.
func LoadSigningKey(path string) (protocol.ECDHPrivateKey, error) {
	if path == "" {
		return nil, refuse(SentenceKeyUnset, errors.New(SigningKeyEnv+" is not set"))
	}

	info, err := os.Stat(path)
	if errors.Is(err, fs.ErrNotExist) {
		return nil, refuse(fmt.Sprintf(SentenceKeyMissingFmt, path), err)
	}
	if err != nil {
		return nil, refuse(fmt.Sprintf(SentenceKeyUnreadableFmt, path), err)
	}
	if !info.Mode().IsRegular() {
		return nil, refuse(fmt.Sprintf(SentenceKeyNotRegularFmt, path), fmt.Errorf("%s is %s", path, info.Mode().Type()))
	}
	if shared := info.Mode().Perm() & sharedModeBits; shared != 0 {
		return nil, refuse(fmt.Sprintf(SentenceKeyPermissionsFmt, path, path), fmt.Errorf("%s has mode %04o", path, info.Mode().Perm()))
	}

	// LoadPrivateKey accepts SEC1 and PKCS8 PEM and rejects any curve other
	// than NIST P-256 (internal/authentication/native.go:175-177), so its
	// refusal covers both "not a key" and "not the right key".
	key, err := protocol.LoadPrivateKey(path)
	if errors.Is(err, fs.ErrPermission) {
		return nil, refuse(fmt.Sprintf(SentenceKeyUnreadableFmt, path), err)
	}
	if err != nil {
		return nil, refuse(fmt.Sprintf(SentenceKeyInvalidFmt, path), fmt.Errorf("loading %s: %s", path, Redact(err.Error())))
	}
	if key == nil {
		return nil, refuse(fmt.Sprintf(SentenceKeyInvalidFmt, path), fmt.Errorf("%s yielded no key", path))
	}
	return key, nil
}
