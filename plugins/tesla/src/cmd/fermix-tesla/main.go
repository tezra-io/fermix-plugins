// Command fermix-tesla is the Fermix Tesla vehicle-command helper: an MCP
// server, spoken over stdio, whose tools sign commands for the operator's car
// with Tesla's official SDK.
//
// The Fermix daemon spawns it as a local plugin process and hands it two
// paths in the environment: FERMIX_PLUGIN_TOKEN_FILE, the daemon-owned OAuth
// token file, and SIGNING_KEY_PATH, the application's prime256v1 private key.
// Both files are read on every command, never cached.
package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/tezra-io/fermix-plugins/plugins/tesla/src/internal/tesla"
)

func main() {
	// stdout carries the JSON-RPC framing, so every diagnostic goes to stderr.
	logf := tesla.StderrLogf(func(line string) {
		fmt.Fprintln(os.Stderr, "fermix-tesla: "+line)
	})

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	opener := tesla.NewLiveOpener(
		os.Getenv(tesla.TokenFileEnv),
		os.Getenv(tesla.SigningKeyEnv),
		tesla.UserAgent(),
		time.Now,
		logf,
	)

	err := tesla.NewServer(opener, time.Now, logf).Run(ctx, &mcp.StdioTransport{})
	if err == nil || errors.Is(err, context.Canceled) {
		return
	}
	logf("exiting: %s", err)
	os.Exit(1)
}
