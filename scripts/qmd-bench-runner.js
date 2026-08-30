// qmd-bench-runner.js - drive @tobilu/qmd's runBenchmark for scripts/wiki-eval.py.
//
// The CLI's `qmd bench --json` is dead upstream (qmd.js reads cli.opts.json while parsed
// values live in cli.values), so this imports the dist directly and flips production mode
// on, exactly as the CLI entry does. The result is written to the file named last on argv
// because the embedding model's first run in a process can print native-build noise to
// stdout; only this file is trusted.
//
//   bun scripts/qmd-bench-runner.js <qmd-pkg-dir> <fixture.json> <out.json>
import { writeFileSync } from "node:fs";

const [pkg, fixture, out] = process.argv.slice(2);
// This seat has no Vulkan SDK and no GPU: with qmd's default "auto" (QMD_LLAMA_GPU unset),
// every process start attempts a Vulkan llama.cpp build, fails (cmake error), then falls
// back to CPU - a multi-minute tax per run. qmd's own override skips straight to the
// prebuilt CPU binary (the upstream NODE_LLAMA_CPP_GPU is ignored: qmd passes `gpu`
// explicitly to getLlama).
process.env.QMD_LLAMA_GPU ||= "false";
const { enableProductionMode } = await import(pkg + "/dist/store.js");
enableProductionMode();
const { runBenchmark } = await import(pkg + "/dist/bench/bench.js");
// bm25 scores the keyword rows and `full` (hybrid + rerank, the `qmd query` pipeline) the
// semantic rows; the vector/hybrid backends are redundant for this eval and ~5x the
// per-query CPU cost (measured on this seat: ~5.4s of ~6.4s per query).
const res = await runBenchmark(fixture, { json: true, backends: ["bm25", "full"] });
writeFileSync(out, JSON.stringify(res, null, 1));
