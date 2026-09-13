package tesla

import "errors"

// The sentences the operator sees. Each one names the single correction that
// unblocks the call; they are part of the contract with the Fermix engine, so
// treat a change here as a change to a published surface.
const (
	SentenceToken             = "Fermix's Tesla sign-in is missing or expired. Sign in again on the setup page."
	SentenceKeyUnset          = "The Tesla signing key is not configured. Set SIGNING_KEY_PATH to the application's private key and try again."
	SentenceKeyMissingFmt     = "No Tesla signing key at %s. Put the application's private key there and try again."
	SentenceKeyNotRegularFmt  = "The Tesla signing key at %s is not a regular file. Point SIGNING_KEY_PATH at the PEM private key file."
	SentenceKeyPermissionsFmt = "The Tesla signing key at %s is readable by other users. Run chmod 600 %s and try again."
	SentenceKeyUnreadableFmt  = "The Tesla signing key at %s could not be read. Check the path and its permissions, then try again."
	SentenceKeyInvalidFmt     = "The Tesla signing key at %s is not a prime256v1 private key. Replace it with the application's P-256 key in PEM form."
	SentenceAsleep            = "The car is asleep. Wake it with tesla_wake_vehicle, then send the command again."
	SentenceUnpaired          = "This car has not paired the application's key. Open https://tesla.com/_ak/fermix.ai in the Tesla app on the owner's phone, approve it, then try again."
	SentenceUnconfirmed       = "The command was sent but the car did not confirm. Check the car's state before sending it again."
	SentenceNoResponse        = "The car did not respond in time. Try again in a moment."

	SentenceVIN              = "A Tesla VIN is exactly 17 characters; call tesla_list_vehicles for the car's VIN."
	SentenceMissingArgFmt    = "%s is required for this command."
	SentenceUnexpectedArgFmt = "This command does not take %s."
	SentenceIntRangeFmt      = "%s must be a whole number between %d and %d."
	SentenceCelsiusRangeFmt  = "%s must be between %g and %g degrees Celsius."
	SentenceArguments        = "This command's arguments were not understood; check the tool's schema and send them again."
)

// A Refusal is an error the operator is meant to read. Sentence is published
// verbatim as the tool's error text; Cause carries the detail that explains it
// and is logged (redacted) rather than published, so a diagnosis is never lost
// and a credential is never shown.
type Refusal struct {
	Sentence string
	Cause    error
}

func (r *Refusal) Error() string { return r.Sentence }

func (r *Refusal) Unwrap() error { return r.Cause }

// refuse builds a Refusal, asserting that the caller supplied both halves.
func refuse(sentence string, cause error) *Refusal {
	if sentence == "" {
		panic("tesla: refusal without a sentence")
	}
	if cause == nil {
		panic("tesla: refusal without a cause")
	}
	return &Refusal{Sentence: sentence, Cause: cause}
}

// Explain returns the one sentence to publish for err. An error this package
// classified carries its own sentence; anything else is surfaced as the
// underlying library's own words, redacted of credential material.
func Explain(err error) string {
	if err == nil {
		return ""
	}
	var refusal *Refusal
	if errors.As(err, &refusal) {
		return refusal.Sentence
	}
	return Redact(err.Error())
}
