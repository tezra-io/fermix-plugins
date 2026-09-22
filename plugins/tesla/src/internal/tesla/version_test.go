package tesla_test

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/tezra-io/fermix-plugins/plugins/tesla/src/internal/tesla"
)

// The catalog takes the plugin's version from plugin.json; the helper reports
// tesla.Version in its MCP server info and its user agent. They are read by
// different tools, so this is the one place that holds them together: a
// release whose helper still reports the previous version is refused here,
// before the release lane signs it.
func TestVersionMatchesManifest(t *testing.T) {
	path := filepath.Join("..", "..", "..", "plugin.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	var manifest struct {
		Version string `json:"version"`
	}
	if err := json.Unmarshal(raw, &manifest); err != nil {
		t.Fatalf("parse %s: %v", path, err)
	}
	if manifest.Version == "" {
		t.Fatalf("%s carries no version", path)
	}
	if manifest.Version != tesla.Version {
		t.Fatalf("plugin.json is %s but the helper reports %s: bump internal/tesla/version.go", manifest.Version, tesla.Version)
	}
}
