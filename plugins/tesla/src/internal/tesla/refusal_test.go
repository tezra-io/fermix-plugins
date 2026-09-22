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
	links := strings.Count(sentence, "https://tesla.com/_ak/")
	placeholders := strings.Count(sentence, "https://tesla.com/_ak/<your-domain>")
	if links == 0 {
		t.Fatalf("unpaired sentence must give the pairing link, got %q", sentence)
	}
	if links != placeholders {
		t.Fatalf("every pairing link must carry the operator's own domain as a placeholder, never a fixed host, got %q", sentence)
	}
}
