package tesla_test

import (
	"encoding/json"
	"os"
	"path/filepath"
	"slices"
	"testing"

	"github.com/tezra-io/fermix-plugins/plugins/tesla/src/internal/tesla"
)

// The manifest is what Fermix reads: its mcp-rail entries preview the tools
// this helper advertises, and "access_sensitive": true on one of them is what
// the daemon holds for the owner's confirmation. Command.AccessSensitive only
// sets the MCP destructive hint. The two are read by different programs, so
// this is the one place that holds them together: a command flagged on one
// side and not the other fails here, before the release lane signs it.
func TestManifestAccessSensitiveMatchesTheHelper(t *testing.T) {
	previews, flagged := manifestPreviews(t)

	var advertised, sensitive []string
	for _, cmd := range tesla.Commands() {
		advertised = append(advertised, "tesla_"+cmd.Name)
		if cmd.AccessSensitive {
			sensitive = append(sensitive, "tesla_"+cmd.Name)
		}
	}
	slices.Sort(advertised)
	slices.Sort(sensitive)

	if !slices.Equal(previews, advertised) {
		t.Errorf("plugin.json mcp previews = %v\nhelper advertises %v", previews, advertised)
	}
	if !slices.Equal(flagged, sensitive) {
		t.Errorf("plugin.json flags %v as access_sensitive\nhelper marks %v", flagged, sensitive)
	}
}

// manifestPreviews returns the sorted names of plugin.json's mcp-rail
// entries, and of those among them that carry "access_sensitive": true.
func manifestPreviews(t *testing.T) (previews, flagged []string) {
	t.Helper()
	path := filepath.Join("..", "..", "..", "plugin.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	var manifest struct {
		Tools []struct {
			Name            string `json:"name"`
			Rail            string `json:"rail"`
			AccessSensitive bool   `json:"access_sensitive"`
		} `json:"tools"`
	}
	if err := json.Unmarshal(raw, &manifest); err != nil {
		t.Fatalf("parse %s: %v", path, err)
	}

	for _, tool := range manifest.Tools {
		if tool.Rail != "mcp" {
			continue
		}
		previews = append(previews, tool.Name)
		if tool.AccessSensitive {
			flagged = append(flagged, tool.Name)
		}
	}
	slices.Sort(previews)
	slices.Sort(flagged)
	return previews, flagged
}
