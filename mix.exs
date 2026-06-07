defmodule FermixPlugins.MixProject do
  use Mix.Project

  def project do
    [
      apps_path: "apps",
      version: "0.1.0",
      start_permanent: Mix.env() == :prod,
      deps: deps(),
      aliases: aliases()
    ]
  end

  def cli do
    [preferred_envs: [check: :test]]
  end

  defp deps, do: []

  defp aliases do
    [
      check: ["format --check-formatted", "credo --strict", "test"]
    ]
  end
end
