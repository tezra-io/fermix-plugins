defmodule FermixOpik.MapperTest do
  use ExUnit.Case, async: true

  alias FermixOpik.Mapper

  @ended ~U[2026-06-02 12:00:03.200Z]

  test "llm_span carries model, provider, and OpenAI-style usage for auto-cost" do
    metadata = %{
      provider: :openai_codex,
      model: "gpt-5-codex",
      status: :ok,
      tokens: %{prompt: 100, completion: 25}
    }

    span =
      Mapper.llm_span(metadata, %{duration_ms: 1_200},
        trace_id: "trace-1",
        parent_span_id: "wrap-1",
        project_name: "fermix",
        ended: @ended
      )

    assert span.type == "llm"
    assert span.trace_id == "trace-1"
    assert span.parent_span_id == "wrap-1"
    assert span.model == "gpt-5-codex"
    # Codex maps to the "openai" pricing provider Opik recognizes
    assert span.provider == "openai"
    assert span.usage == %{prompt_tokens: 100, completion_tokens: 25, total_tokens: 125}
    assert span.start_time == "2026-06-02T12:00:02.000Z"
    assert span.end_time == "2026-06-02T12:00:03.200Z"
  end

  test "tool_span records name, type, and preserves plugin metadata" do
    metadata = %{tool: "shell", success: true, plugin: "builtin", action: "navigate"}

    span =
      Mapper.tool_span(metadata, %{duration_ms: 50},
        trace_id: "trace-1",
        parent_span_id: "wrap-1",
        project_name: "fermix",
        ended: @ended
      )

    assert span.type == "tool"
    assert span.name == "shell"
    assert span.metadata == %{plugin: "builtin", action: "navigate"}
  end

  test "content fields wrap into Opik input/output when present" do
    metadata = %{tool: "shell", input: "ls -la", output: "a\nb"}

    span =
      Mapper.tool_span(metadata, %{duration_ms: 10},
        trace_id: "t",
        parent_span_id: nil,
        project_name: "fermix",
        ended: @ended
      )

    assert span.input == %{text: "ls -la"}
    assert span.output == %{text: "a\nb"}
    refute Map.has_key?(span, :parent_span_id)
  end

  test "error metadata becomes error_info" do
    metadata = %{tool: "file_read", success: false, error: "not found"}

    span =
      Mapper.tool_span(metadata, %{duration_ms: 1},
        trace_id: "t",
        project_name: "fermix",
        ended: @ended
      )

    assert span.error_info == %{exception_type: "ToolError", message: "not found"}
  end

  test "usage tolerates *_tokens keys and derives total" do
    assert Mapper.usage(%{prompt_tokens: 3, completion_tokens: 7}) ==
             %{prompt_tokens: 3, completion_tokens: 7, total_tokens: 10}

    assert Mapper.usage(%{}) == nil
    assert Mapper.usage(nil) == nil
  end

  test "provider_string maps every Fermix provider to an Opik pricing token" do
    assert Mapper.provider_string(:openai) == "openai"
    assert Mapper.provider_string(:openai_codex) == "openai"
    assert Mapper.provider_string(:anthropic) == "anthropic"
    assert Mapper.provider_string(:xai) == "xai"
    assert Mapper.provider_string(nil) == nil
  end
end
