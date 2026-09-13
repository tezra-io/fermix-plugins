package tesla_test

import (
	"context"
	"encoding/json"
	"fmt"
	"slices"
	"strings"
	"testing"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/teslamotors/vehicle-command/pkg/protocol"
	"github.com/tezra-io/fermix-plugins/plugins/tesla/src/internal/tesla"
)

// connectServer wires a client to a fermix-tesla server over an in-memory
// transport and returns the session plus whatever the server logged.
func connectServer(t *testing.T, opener tesla.Opener) (*mcp.ClientSession, *strings.Builder) {
	t.Helper()

	var logged strings.Builder
	logf := func(format string, args ...any) {
		fmt.Fprintf(&logged, format+"\n", args...)
	}
	server := tesla.NewServer(opener, fixedClock(), logf)

	serverTransport, clientTransport := mcp.NewInMemoryTransports()
	serverSession, err := server.Connect(context.Background(), serverTransport, nil)
	if err != nil {
		t.Fatalf("server connect: %v", err)
	}
	t.Cleanup(func() { _ = serverSession.Close() })

	client := mcp.NewClient(&mcp.Implementation{Name: "test-client", Version: "0.0.0"}, nil)
	clientSession, err := client.Connect(context.Background(), clientTransport, nil)
	if err != nil {
		t.Fatalf("client connect: %v", err)
	}
	t.Cleanup(func() { _ = clientSession.Close() })

	return clientSession, &logged
}

func TestServerAdvertisesExactlyTheShippedTools(t *testing.T) {
	session, _ := connectServer(t, &fakeOpener{vehicle: &fakeVehicle{}})

	listed, err := session.ListTools(context.Background(), nil)
	if err != nil {
		t.Fatalf("tools/list: %v", err)
	}

	var names []string
	for _, tool := range listed.Tools {
		names = append(names, tool.Name)
	}
	slices.Sort(names)
	want := slices.Clone(shippedTools)
	slices.Sort(want)
	if !slices.Equal(names, want) {
		t.Errorf("tools/list = %v\nwant %v", names, want)
	}
}

func TestServerAdvertisesBoundedSchemas(t *testing.T) {
	session, _ := connectServer(t, &fakeOpener{vehicle: &fakeVehicle{}})

	listed, err := session.ListTools(context.Background(), nil)
	if err != nil {
		t.Fatalf("tools/list: %v", err)
	}

	schemas := map[string]map[string]any{}
	for _, tool := range listed.Tools {
		body, err := json.Marshal(tool.InputSchema)
		if err != nil {
			t.Fatalf("marshalling %s schema: %v", tool.Name, err)
		}
		var schema map[string]any
		if err := json.Unmarshal(body, &schema); err != nil {
			t.Fatalf("decoding %s schema: %v", tool.Name, err)
		}
		schemas[tool.Name] = schema
	}

	for _, name := range shippedTools {
		schema, ok := schemas[name]
		if !ok {
			t.Fatalf("%s was not advertised", name)
		}
		properties, _ := schema["properties"].(map[string]any)
		vin, _ := properties["vin"].(map[string]any)
		if vin["minLength"] != float64(17) || vin["maxLength"] != float64(17) {
			t.Errorf("%s vin bounds = %v", name, vin)
		}
		if required, _ := schema["required"].([]any); len(required) == 0 || required[0] != "vin" {
			t.Errorf("%s required = %v", name, schema["required"])
		}
	}

	limit := schemas["set_charge_limit"]["properties"].(map[string]any)["percent"].(map[string]any)
	if limit["minimum"] != float64(50) || limit["maximum"] != float64(100) {
		t.Errorf("set_charge_limit percent bounds = %v", limit)
	}
	amps := schemas["set_charging_amps"]["properties"].(map[string]any)["amps"].(map[string]any)
	if amps["minimum"] != float64(1) || amps["maximum"] != float64(48) {
		t.Errorf("set_charging_amps amps bounds = %v", amps)
	}
	cabin := schemas["set_cabin_temperature"]
	cabinRequired, _ := cabin["required"].([]any)
	if !slices.Contains(cabinRequired, any("driver_celsius")) {
		t.Errorf("set_cabin_temperature required = %v", cabinRequired)
	}
	if slices.Contains(cabinRequired, any("passenger_celsius")) {
		t.Errorf("passenger_celsius must be optional, required = %v", cabinRequired)
	}
}

func TestServerRefusesAShortVINBeforeAnyNetworkUse(t *testing.T) {
	opener := &fakeOpener{vehicle: &fakeVehicle{}}
	session, _ := connectServer(t, opener)

	result, err := session.CallTool(context.Background(), &mcp.CallToolParams{
		Name:      "unlock_doors",
		Arguments: map[string]any{"vin": "5YJ3E1EA7KF00031"},
	})
	if err != nil {
		t.Fatalf("tools/call: %v", err)
	}

	if !result.IsError {
		t.Error("a 16-character VIN was accepted")
	}
	if got := publishedText(t, result); got != tesla.SentenceVIN {
		t.Errorf("published text = %q, want %q", got, tesla.SentenceVIN)
	}
	if opener.opens != 0 {
		t.Errorf("opens = %d, want 0: nothing may reach Tesla for a malformed VIN", opener.opens)
	}
}

func TestServerReturnsTheResultJSONAsItsOnlyContent(t *testing.T) {
	opener := &fakeOpener{vehicle: &fakeVehicle{}}
	session, _ := connectServer(t, opener)

	result, err := session.CallTool(context.Background(), &mcp.CallToolParams{
		Name:      "set_charge_limit",
		Arguments: map[string]any{"vin": goodVIN, "percent": 80},
	})
	if err != nil {
		t.Fatalf("tools/call: %v", err)
	}

	if result.IsError {
		t.Fatalf("unexpected error result: %+v", result.Content)
	}
	if len(result.Content) != 1 {
		t.Fatalf("content = %d blocks, want exactly 1", len(result.Content))
	}
	text, ok := result.Content[0].(*mcp.TextContent)
	if !ok {
		t.Fatalf("content block is %T, want *mcp.TextContent", result.Content[0])
	}

	var body tesla.Result
	if err := json.Unmarshal([]byte(text.Text), &body); err != nil {
		t.Fatalf("content is not the agreed JSON: %v (%q)", err, text.Text)
	}
	want := tesla.Result{Command: "set_charge_limit", VIN: goodVIN, Result: true, DispatchedAt: "2026-09-13T12:34:56Z"}
	if body != want {
		t.Errorf("body = %+v, want %+v", body, want)
	}
	if opener.vin != goodVIN {
		t.Errorf("opened vin = %q, want %q", opener.vin, goodVIN)
	}
}

func TestServerPublishesTheSentenceAndLogsTheCause(t *testing.T) {
	opener := &fakeOpener{vehicle: &fakeVehicle{sessionErr: protocol.ErrKeyNotPaired}}
	session, logged := connectServer(t, opener)

	result, err := session.CallTool(context.Background(), &mcp.CallToolParams{
		Name:      "lock_doors",
		Arguments: map[string]any{"vin": goodVIN},
	})
	if err != nil {
		t.Fatalf("tools/call: %v", err)
	}

	if !result.IsError {
		t.Fatal("want an error result")
	}
	text, ok := result.Content[0].(*mcp.TextContent)
	if !ok {
		t.Fatalf("content block is %T", result.Content[0])
	}
	if text.Text != tesla.SentenceUnpaired {
		t.Errorf("published text = %q, want %q", text.Text, tesla.SentenceUnpaired)
	}
	if !strings.Contains(logged.String(), "lock_doors") {
		t.Errorf("stderr did not name the tool: %q", logged.String())
	}
	if !strings.Contains(logged.String(), "has not been paired") {
		t.Errorf("stderr did not carry the SDK's own words: %q", logged.String())
	}
}

func TestServerReportsANominalRefusalAsASuccessfulCall(t *testing.T) {
	nominal := &protocol.NominalError{Details: protocol.NewError("car could not execute command: charge_port_door_open", false, false)}
	opener := &fakeOpener{vehicle: &fakeVehicle{executeErr: nominal}}
	session, _ := connectServer(t, opener)

	result, err := session.CallTool(context.Background(), &mcp.CallToolParams{
		Name:      "open_charge_port",
		Arguments: map[string]any{"vin": goodVIN},
	})
	if err != nil {
		t.Fatalf("tools/call: %v", err)
	}

	if result.IsError {
		t.Fatal("a nominal vehicle refusal must not be an error result")
	}
	text := result.Content[0].(*mcp.TextContent).Text
	var body tesla.Result
	if err := json.Unmarshal([]byte(text), &body); err != nil {
		t.Fatalf("content is not the agreed JSON: %v", err)
	}
	if body.Result {
		t.Error("result = true, want false")
	}
	if !strings.Contains(body.Reason, "charge_port_door_open") {
		t.Errorf("reason = %q", body.Reason)
	}
}

func TestServerRefusesAnArgumentTheToolDoesNotTake(t *testing.T) {
	opener := &fakeOpener{vehicle: &fakeVehicle{}}
	session, _ := connectServer(t, opener)

	result, err := session.CallTool(context.Background(), &mcp.CallToolParams{
		Name:      "honk_horn",
		Arguments: map[string]any{"vin": goodVIN, "percent": 80},
	})
	if err != nil {
		t.Fatalf("tools/call: %v", err)
	}

	if !result.IsError {
		t.Error("honk_horn accepted an argument it does not take")
	}
	if got, want := publishedText(t, result), fmt.Sprintf(tesla.SentenceUnexpectedArgFmt, "percent"); got != want {
		t.Errorf("published text = %q, want %q", got, want)
	}
	if opener.opens != 0 {
		t.Errorf("opens = %d, want 0", opener.opens)
	}
}

func TestServerRefusesAnOutOfRangeChargeLimit(t *testing.T) {
	opener := &fakeOpener{vehicle: &fakeVehicle{}}
	session, _ := connectServer(t, opener)

	result, err := session.CallTool(context.Background(), &mcp.CallToolParams{
		Name:      "set_charge_limit",
		Arguments: map[string]any{"vin": goodVIN, "percent": 120},
	})
	if err != nil {
		t.Fatalf("tools/call: %v", err)
	}

	if !result.IsError {
		t.Error("a 120% charge limit was accepted")
	}
	if got, want := publishedText(t, result), fmt.Sprintf(tesla.SentenceIntRangeFmt, "percent", 50, 100); got != want {
		t.Errorf("published text = %q, want %q", got, want)
	}
	if opener.opens != 0 {
		t.Errorf("opens = %d, want 0", opener.opens)
	}
}

// publishedText returns the single text block a tool result carries.
func publishedText(t *testing.T, result *mcp.CallToolResult) string {
	t.Helper()
	if len(result.Content) != 1 {
		t.Fatalf("content = %d blocks, want exactly 1", len(result.Content))
	}
	text, ok := result.Content[0].(*mcp.TextContent)
	if !ok {
		t.Fatalf("content block is %T, want *mcp.TextContent", result.Content[0])
	}
	return text.Text
}

// A refusal the caller cannot act on is a refusal nobody can fix. Every way of
// getting the arguments wrong must come back in this package's own words.
func TestServerRefusalsAlwaysSpeakThisPackagesSentences(t *testing.T) {
	cases := []struct {
		name string
		tool string
		args map[string]any
		want string
	}{
		{"no arguments at all", "honk_horn", nil, tesla.SentenceVIN},
		{"vin of the wrong length", "honk_horn", map[string]any{"vin": "TOO-SHORT"}, tesla.SentenceVIN},
		{"unknown argument", "honk_horn", map[string]any{"vin": goodVIN, "nonsense": 1}, tesla.SentenceArguments},
		{"argument of the wrong type", "set_charge_limit", map[string]any{"vin": goodVIN, "percent": "eighty"}, tesla.SentenceArguments},
		{"required argument missing", "set_charge_limit", map[string]any{"vin": goodVIN}, fmt.Sprintf(tesla.SentenceMissingArgFmt, "percent")},
		{"amps out of range", "set_charging_amps", map[string]any{"vin": goodVIN, "amps": 64}, fmt.Sprintf(tesla.SentenceIntRangeFmt, "amps", 1, 48)},
		{"cabin temperature out of range", "set_cabin_temperature", map[string]any{"vin": goodVIN, "driver_celsius": 30}, fmt.Sprintf(tesla.SentenceCelsiusRangeFmt, "driver_celsius", 15.0, 28.0)},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			opener := &fakeOpener{vehicle: &fakeVehicle{}}
			session, _ := connectServer(t, opener)

			result, err := session.CallTool(context.Background(), &mcp.CallToolParams{Name: tc.tool, Arguments: tc.args})
			if err != nil {
				t.Fatalf("tools/call: %v", err)
			}
			if !result.IsError {
				t.Fatalf("%s accepted %v", tc.tool, tc.args)
			}
			if got := publishedText(t, result); got != tc.want {
				t.Errorf("published text = %q, want %q", got, tc.want)
			}
			if opener.opens != 0 {
				t.Errorf("opens = %d, want 0", opener.opens)
			}
		})
	}
}
