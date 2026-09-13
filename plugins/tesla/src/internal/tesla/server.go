package tesla

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// callTimeout bounds one whole tool call: reading the token and key, opening
// the connection, the handshake, the command, and the answer. One deadline
// covers all of it, so a stalled car cannot hold a plugin process open.
const callTimeout = 30 * time.Second

// Logf writes one diagnostic line. Everything passed to it is redacted before
// it is written.
type Logf func(format string, args ...any)

// NewServer builds the MCP server this binary serves over stdio.
func NewServer(opener Opener, now func() time.Time, logf Logf) *mcp.Server {
	if opener == nil || now == nil || logf == nil {
		panic("tesla: NewServer needs an opener, a clock and a logger")
	}

	server := mcp.NewServer(&mcp.Implementation{
		Name:    "fermix-tesla",
		Title:   "Fermix Tesla vehicle commands",
		Version: Version,
	}, nil)

	for _, cmd := range Commands() {
		register(server, opener, cmd, now, logf)
	}
	return server
}

// register adds one command to the server.
//
// The handler is the untyped one on purpose. The SDK's generic AddTool would
// validate arguments against the advertised schema and publish its validator's
// own wording, which would leave this package's refusals — the ones the tests
// exercise and the ones that name the correction — unreachable over the wire.
// The schema is what the model reads; Command.Validate is what every call is
// held to, and there is exactly one of it.
//
// Every tool here changes the state of a physical car, so none is read-only or
// idempotent.
func register(server *mcp.Server, opener Opener, cmd *Command, now func() time.Time, logf Logf) {
	destructive := false
	openWorld := true
	tool := &mcp.Tool{
		Name:        cmd.Name,
		Description: cmd.Description,
		InputSchema: cmd.Schema,
		Annotations: &mcp.ToolAnnotations{
			ReadOnlyHint:    false,
			IdempotentHint:  false,
			DestructiveHint: &destructive,
			OpenWorldHint:   &openWorld,
		},
	}

	server.AddTool(tool, func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		ctx, cancel := context.WithTimeout(ctx, callTimeout)
		defer cancel()

		args, err := decodeArgs(req.Params.Arguments)
		if err != nil {
			return refused(cmd, err, logf), nil
		}

		result, err := Run(ctx, opener, cmd, args, now)
		if err != nil {
			return refused(cmd, err, logf), nil
		}

		body, err := json.Marshal(result)
		if err != nil {
			logf("%s could not encode its result: %s", cmd.Name, Redact(err.Error()))
			return errorResult("The command reached the car but its result could not be encoded."), nil
		}
		return &mcp.CallToolResult{Content: []mcp.Content{&mcp.TextContent{Text: string(body)}}}, nil
	})
}

// decodeArgs reads the call's arguments. Unknown keys are refused rather than
// dropped: a misspelled argument must not look like an argument that was left
// out.
func decodeArgs(raw json.RawMessage) (Args, error) {
	var args Args
	if len(raw) == 0 {
		// No arguments at all. Validate refuses it for the missing VIN, which
		// is the correction worth naming.
		return args, nil
	}

	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&args); err != nil {
		return Args{}, refuse(SentenceArguments, err)
	}
	return args, nil
}

// refused logs the detail and publishes the sentence.
func refused(cmd *Command, err error, logf Logf) *mcp.CallToolResult {
	logf("%s refused: %s", cmd.Name, cause(err))
	return errorResult(Explain(err))
}

func errorResult(sentence string) *mcp.CallToolResult {
	return &mcp.CallToolResult{
		IsError: true,
		Content: []mcp.Content{&mcp.TextContent{Text: sentence}},
	}
}

// cause returns the detail behind a refusal for the log, redacted. The
// operator reads the sentence; whoever debugs this reads the cause, and
// neither ever sees a token or a key.
func cause(err error) string {
	var refusal *Refusal
	if errors.As(err, &refusal) && refusal.Cause != nil {
		return Redact(refusal.Cause.Error())
	}
	return Redact(err.Error())
}

// StderrLogf builds a Logf that writes redacted lines to w.
func StderrLogf(write func(string)) Logf {
	return func(format string, args ...any) {
		write(Redact(fmt.Sprintf(format, args...)))
	}
}
