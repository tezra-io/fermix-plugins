package tesla_test

import (
	"strings"
	"testing"

	"github.com/tezra-io/fermix-plugins/plugins/tesla/src/internal/tesla"
)

// Every operator registers their own application domain, and a car trusts the
// key published on the domain it paired. A pairing link that names a fixed host
// sends the operator to pair someone else's key: their own commands still fail,
// and the holder of that key's private half gains a key to their car.
func TestUnpairedSentenceNamesNoFixedDomain(t *testing.T) {
	sentence := tesla.SentenceUnpaired
	if !strings.Contains(sentence, "https://tesla.com/_ak/<your-domain>") {
		t.Fatalf("unpaired sentence must give the pairing link with the operator's own domain as a placeholder, got %q", sentence)
	}
	if strings.Contains(sentence, "fermix.ai") {
		t.Fatalf("unpaired sentence must not name a fixed domain, got %q", sentence)
	}
}
