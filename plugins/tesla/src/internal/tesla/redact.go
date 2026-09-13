package tesla

import (
	"regexp"
	"strings"
)

// This binary handles two kinds of material that must never reach a log, a
// tool result or an error message: the operator's OAuth access token and the
// application's private key. Both can arrive inside text we did not author —
// notably Tesla's own SDK, whose account.New quotes the offending token's
// payload verbatim when it fails to parse it (pkg/account/account.go:126).
// Every string that leaves this process on stderr or in a refusal passes
// through Redact first.
var (
	pemBlockPattern = regexp.MustCompile(`(?s)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----`)
	bearerPattern   = regexp.MustCompile(`(?i)\bbearer\s+\S+`)
	jwtPattern      = regexp.MustCompile(`\b[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b`)
	// A single base64url run, which is what one segment of a token looks like
	// once the SDK has torn the token apart. Whether it is credential material
	// or the library's own vocabulary is decided by looksOpaque.
	longRunPattern = regexp.MustCompile(`[A-Za-z0-9_-]{32,}`)
)

const redacted = "[redacted]"

// Redact removes credential material from text while leaving the diagnosis
// that surrounds it intact.
func Redact(text string) string {
	text = pemBlockPattern.ReplaceAllString(text, redacted)
	text = bearerPattern.ReplaceAllString(text, "Bearer "+redacted)
	text = jwtPattern.ReplaceAllString(text, redacted)
	return longRunPattern.ReplaceAllStringFunc(text, redactOpaque)
}

func redactOpaque(run string) string {
	if looksOpaque(run) {
		return redacted
	}
	return run
}

// looksOpaque reports whether a long unbroken run is encoded material rather
// than prose. Base64 mixes upper case, lower case and digits in one word; the
// SDK's own long identifiers do not — they are either SCREAMING_SNAKE_CASE
// constants or lower_snake_case names, so neither is touched.
func looksOpaque(run string) bool {
	return strings.ContainsFunc(run, isLowerASCII) &&
		strings.ContainsFunc(run, isUpperASCII) &&
		strings.ContainsFunc(run, isASCIIDigit)
}

func isLowerASCII(r rune) bool { return r >= 'a' && r <= 'z' }

func isUpperASCII(r rune) bool { return r >= 'A' && r <= 'Z' }

func isASCIIDigit(r rune) bool { return r >= '0' && r <= '9' }
