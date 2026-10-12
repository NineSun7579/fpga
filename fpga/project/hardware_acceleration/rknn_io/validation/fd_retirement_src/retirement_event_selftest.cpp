// Pure lifecycle/report integration. Never constructs Api or loads any runtime.
#define main unused_benchmark_main
#include "../../bench.cpp"
#undef main
#define main unused_lifecycle_main
#include "../../dma_heap_import_selftest.cpp"
#undef main

int main() {
    try {
        for (const QString &branch : {QString("success"), QString("failed_run"), QString("run_no_return"), QString("failed_context")}) {
            Mock m; rknn_context ctx = 123;
            MemorySessionOwnedRAII owned(m, ctx, m.runtime);
            auto &b = owned.allocate(25600, "test_buffer");
            if (branch == "failed_context") m.contextRc = -1;
            else {
                owned.beforeRun();
                if (branch != "run_no_return") owned.runReturned(branch == "failed_run" ? -1 : 0);
            }
            const bool ok = owned.retire();
            require(ok == (branch == "success"), "retirement outcome");
            // Simulate an invalid device-owned descriptor after failure; reporting
            // and rejected validation must use bookkeeping without reading it.
            if (branch == "failed_run" || branch == "run_no_return")
                b.memory = reinterpret_cast<rknn_tensor_mem *>(uintptr_t(1));
            rejected([&] { owned.validate(b); });
            const auto row = importedRetirementJson(owned, m.runtime, "mock_" + branch, ok);
            const auto buffer = row["buffers"].toArray()[0].toObject();
            if (branch == "failed_run" || branch == "run_no_return") {
                require(row["retirement_branch"] == "uncertain_run_process_teardown" && row["context_destroy_rc"].isNull() &&
                        !row["context_destroy_attempted"].toBool() && row["context_destroy_skipped"].toBool(), "skipped context RC was fabricated");
                require(buffer["destroy_mem_rc"].isNull() && buffer["destroy_mem_skipped"].toBool() &&
                        !buffer["before_destroy_inspected"].toBool(), "skipped import/inspection was fabricated");
                retainedWithoutRelease(m);
            }
            if (!ok) {
                require(row["context_retained"].toBool() && row["retained_context_hex"] == "7b" &&
                        row["process_teardown_only"].toBool() && row["runtime_library_retained"].toBool() &&
                        row["fatal_no_continue"].toBool(), "retained context/library reporting");
                require(buffer["munmap_rc"].isNull() && buffer["close_rc"].isNull() &&
                        !buffer["munmap_attempted"].toBool() && !buffer["close_attempted"].toBool(), "skipped release RC was fabricated");
                const int before = unloadCalls;
                require(!m.runtime.unload(&m, &mockUnload) && unloadCalls == before, "deferred unload attempted");
            }
            if (branch == "failed_context") require(row["context_destroy_rc"].toInt() == -1 &&
                row["context_destroy_attempted"].toBool() && buffer["destroy_mem_attempted"].toBool() &&
                !buffer["after_context_destroy_inspected"].toBool(), "failed context RC/attempt reporting");
            emitJson(row);
        }
        return 0;
    } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 1; }
}
