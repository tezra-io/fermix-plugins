// Package tesla implements the Fermix Tesla vehicle-command helper: it loads
// the daemon-issued OAuth token and the operator's signing key, signs one
// vehicle command with Tesla's official SDK, and reports the outcome in the
// shape the Fermix engine expects.
package tesla

import "os"

// Version is the helper's own version. It must be kept in step with the
// `version` field of plugins/tesla/plugin.json; the two are read by different
// tools and neither can see the other.
const Version = "1.0.0"

// userAgentOverride names the environment variable that replaces the default
// user agent. Tesla's SDK appends its own "tesla-sdk/<version>" token to
// whatever we pass, so this only controls the leading application segment.
const userAgentOverride = "FERMIX_TESLA_USER_AGENT"

// UserAgent returns the application segment of the HTTP user agent used for
// every Fleet API call.
func UserAgent() string {
	if override := os.Getenv(userAgentOverride); override != "" {
		return override
	}
	return "fermix-tesla/" + Version
}
