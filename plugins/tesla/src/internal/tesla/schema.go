package tesla

import "github.com/google/jsonschema-go/jsonschema"

// A param is one advertised argument beyond the VIN.
type param struct {
	name     string
	schema   *jsonschema.Schema
	required bool
}

// inputSchema renders a command's arguments as the JSON schema the engine and
// the model read. It is built from the same param list the validator uses, so
// the advertised bounds and the enforced bounds cannot drift apart.
//
// The schema is the first of two gates. The MCP SDK validates arguments
// against it before the handler runs, which keeps malformed input off the
// command path; Command.Validate then enforces the same bounds in process, so
// the guarantee holds for any caller, not only a schema-respecting one.
func inputSchema(params []param) *jsonschema.Schema {
	properties := map[string]*jsonschema.Schema{"vin": vinSchema()}
	order := []string{"vin"}
	required := []string{"vin"}

	for _, p := range params {
		properties[p.name] = p.schema
		order = append(order, p.name)
		if p.required {
			required = append(required, p.name)
		}
	}

	return &jsonschema.Schema{
		Type:                 "object",
		Properties:           properties,
		PropertyOrder:        order,
		Required:             required,
		AdditionalProperties: &jsonschema.Schema{Not: &jsonschema.Schema{}},
	}
}

func vinSchema() *jsonschema.Schema {
	length := vinLength
	return &jsonschema.Schema{
		Type:        "string",
		Description: "The car's 17-character VIN, from tesla_list_vehicles.",
		MinLength:   &length,
		MaxLength:   &length,
	}
}

func integerSchema(low, high int, description string) *jsonschema.Schema {
	minimum, maximum := float64(low), float64(high)
	return &jsonschema.Schema{
		Type:        "integer",
		Description: description,
		Minimum:     &minimum,
		Maximum:     &maximum,
	}
}

func numberSchema(low, high float64, description string) *jsonschema.Schema {
	minimum, maximum := low, high
	return &jsonschema.Schema{
		Type:        "number",
		Description: description,
		Minimum:     &minimum,
		Maximum:     &maximum,
	}
}

func booleanSchema(description string) *jsonschema.Schema {
	return &jsonschema.Schema{Type: "boolean", Description: description}
}
