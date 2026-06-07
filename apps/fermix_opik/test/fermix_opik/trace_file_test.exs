defmodule FermixOpik.TraceFileTest do
  use ExUnit.Case, async: true

  alias FermixOpik.Aggregation
  alias FermixOpik.TraceFile

  test "normalizes an llm_call row into a provider.call event with usage" do
    row = %{
      "ts" => "2026-06-02T12:00:00.000Z",
      "type" => "llm_call",
      "agent" => "main",
      "duration_ms" => 900,
      "provider" => "openai",
      "model" => "gpt-5",
      "status" => "ok",
      "session_id" => "main-1",
      "tokens" => %{"prompt" => 40, "completion" => 8}
    }

    assert {[:fermix, :provider, :call], %{duration_ms: 900}, meta} =
             TraceFile.normalize("llm_call", row)

    assert meta.session_id == "main-1"
    assert meta.model == "gpt-5"
    assert meta.tokens == %{prompt: 40, completion: 8}
  end

  test "normalizes agent_event rows by their event name" do
    base = %{"ts" => "2026-06-02T12:00:00.000Z", "type" => "agent_event"}

    assert {[:fermix, :agent, :start], %{}, %{session_id: "s", parent_session: "main-1"}} =
             TraceFile.normalize(
               "agent_event",
               Map.merge(base, %{
                 "event" => "agent_start",
                 "session_id" => "s",
                 "parent_session" => "main-1"
               })
             )

    assert {[:fermix, :job, :run_start], %{}, meta} =
             TraceFile.normalize(
               "agent_event",
               Map.merge(base, %{
                 "event" => "job_run_start",
                 "job_id" => "j",
                 "session_id" => "cron_j_1"
               })
             )

    assert meta.job_id == "j"
  end

  test "skips non-trace rows" do
    assert :skip = TraceFile.normalize("channel_msg", %{"ts" => "x"})
    assert :skip = TraceFile.normalize("agent_event", %{"event" => "prompt_context"})
  end

  test "read_events reads a day directory and feeds the aggregator end to end" do
    dir = Path.join(System.tmp_dir!(), "opik_tracefile_#{System.unique_integer([:positive])}")
    day = Path.join(dir, "2026-06-02")
    File.mkdir_p!(day)

    on_exit(fn -> File.rm_rf!(dir) end)

    write(day, "llm_call.jsonl", [
      %{
        ts: "2026-06-02T12:00:00.100Z",
        type: "llm_call",
        agent: "main",
        duration_ms: 100,
        provider: "openai",
        model: "gpt-5",
        status: "ok",
        session_id: "main-1",
        tokens: %{prompt: 5, completion: 2}
      }
    ])

    write(day, "agent_event.jsonl", [
      %{
        ts: "2026-06-02T12:00:00.300Z",
        type: "agent_event",
        event: "turn_complete",
        agent: "main",
        session_id: "main-1",
        channel: "telegram",
        chat_id: "c",
        iterations: 1,
        total_tokens: 7
      }
    ])

    events = TraceFile.read_events(dir)
    # sorted by ts: llm_call first, then turn_complete
    assert [{[:fermix, :provider, :call], _, _, _}, {[:fermix, :agent, :message], _, _, _}] =
             events

    agg = Aggregation.new(project: "fermix", ttl_ms: 1_000_000)

    {_agg, closed} =
      Enum.reduce(events, {agg, []}, fn {ev, meas, meta, at}, {a, acc} ->
        {a, new} =
          Aggregation.apply_event(a, ev, meas, meta, %{
            at: at,
            mono: DateTime.to_unix(at, :microsecond)
          })

        {a, acc ++ new}
      end)

    assert [%{trace: trace, spans: spans}] = closed
    assert trace.name == "agent:main"
    assert Enum.any?(spans, &(&1[:type] == "llm"))
  end

  defp write(dir, file, rows) do
    content = Enum.map_join(rows, &(Jason.encode!(&1) <> "\n"))
    File.write!(Path.join(dir, file), content)
  end
end
