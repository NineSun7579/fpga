#include "rknn_runner.hpp"
#include "platform_binding.hpp"
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <iostream>
#include <sstream>
using namespace paired_bench;
static void write(const std::filesystem::path& path,const void* p,std::size_t n) {
    std::ofstream f(path,std::ios::binary); f.exceptions(std::ios::badbit|std::ios::failbit);
    f.write(static_cast<const char*>(p),std::streamsize(n));
}
static void atomic_json(const std::filesystem::path& path,const QByteArray& bytes) {
    QSaveFile file(QString::fromStdString(path.string()));
    file.setDirectWriteFallback(false);
    require(file.open(QIODevice::WriteOnly),"cannot open atomic evidence file");
    require(file.write(bytes)==bytes.size() && file.commit(),"atomic evidence commit failed");
}
static QJsonObject attr(const rknn_tensor_attr& a) {
    QJsonArray dims; for (unsigned i=0;i<a.n_dims;++i) dims.append(int(a.dims[i]));
    return {{"index",int(a.index)},{"name",a.name},{"dims",dims},{"fmt",int(a.fmt)},
        {"type",int(a.type)},{"qnt_type",int(a.qnt_type)},{"zp",a.zp},{"scale",double(a.scale)},
        {"size",double(a.size)},{"n_elems",double(a.n_elems)},
        {"w_stride",double(a.w_stride)},{"size_with_stride",double(a.size_with_stride)}};
}
static void csv(std::ostream& out,const char* scope,std::size_t block,std::size_t index,int role,
                const Sample& s,const std::string& raw_sha) {
    const auto& d=s.source;
    out<<scope<<','<<block<<','<<index<<','<<role<<','<<d.bank<<','<<d.sequence<<','<<d.generation
        <<','<<d.camera<<','<<d.token<<','<<raw_sha<<','<<s.acquisition.claim_wait<<','<<s.acquisition.raw_copy_ack
        <<','<<s.acquisition.output_copy_ack<<','<<s.acquisition.certification<<','<<s.acquisition.total
        <<','<<s.cpu_prepare<<','<<s.processing<<','<<s.completion_from_capture;
    for (auto time:s.inference.stages) out<<','<<time;
    out<<','<<s.inference.owned.size()<<'\n';
}
int main(int argc,char** argv) {
    if (argc!=5) {
        std::cerr<<"用法：paired_bench 固定模型 外部预留凭据 已持久化generation 输出目录\n";
        return 2;
    }
    const std::filesystem::path dir=argv[4];
    // Keep every owner outside the exception scope: no stack unwinding may
    // release driver mappings/controller lock before the exit policy runs.
    Binding binding;
    ActivationEvidence activation;
    std::uint32_t generation=0;
    std::unique_ptr<Receiver> retained_receiver;
    std::unique_ptr<NpuRunner> retained_runner;
    std::unique_ptr<ExitPolicy> exit_policy;
    std::string failure_reason;
    int result_code=1;
    try {
        install_hold_signals(); // Before any delegate acquisition or blocking I/O.
        std::size_t used=0; auto parsed=std::stoull(argv[3],&used,0);
        require(used==std::string(argv[3]).size() && parsed>0 && parsed<=UINT32_MAX,"generation invalid");
        generation=std::uint32_t(parsed);
        binding=bind_platform(argv[2],generation); // Factory may throw only BEFORE hardware acquisition.
        require(binding.owner && binding.operation_coordinator,"binding missing persistent owner/coordinator");
        activation=binding.owner->activation_evidence();
        exit_policy=std::make_unique<ExitPolicy>(*binding.owner,activation,generation);
        require(activation_valid(activation),"拒绝激活：缺少已验证的有界 driver/provider 与持久 owner 记录");
        require(!termination_requested,"终止请求：尚未激活硬件作业");
        require(binding.arm_request.generation==parsed && binding.output_config.expected_generation==parsed,
                "external generation receipt mismatch");
        retained_receiver=std::make_unique<Receiver>(binding.owner->transport(),*binding.operation_coordinator,
            binding.raw_config,binding.raw_reservation,binding.output_config,binding.output_reservation,
            [] { return termination_requested!=0; });
        auto& receiver=*retained_receiver;
        retained_runner=std::make_unique<NpuRunner>(argv[1]); auto& runner=*retained_runner;
        std::filesystem::create_directories(dir);
        receiver.arm(binding.arm_request); // Explicit receipt, exactly one ARM attempt.
        for (unsigned i=0;i<30;++i) {
            const auto begin=Clock::now(); const auto& pair=receiver.acquire();
            process(runner,Profile::Baseline,pair,begin); process(runner,Profile::Cooperative,pair,begin);
            receiver.recycle();
        }
        QJsonArray captures; std::vector<std::string> paired_sha;
        auto result=run(receiver,runner,240,4,30,[&](std::size_t i,const Pair& pair) {
            auto prefix="pair_"+std::to_string(i);
            write(dir/(prefix+".raw565"),pair.raw.bytes.data(),pair.raw.bytes.size());
            write(dir/(prefix+".rgb640"),pair.output.bytes.data(),pair.output.bytes.size());
            auto rh=sha256(pair.raw.bytes.data(),pair.raw.bytes.size()); paired_sha.push_back(rh);
            const auto& r=pair.raw.descriptor; const auto& p=pair.output.descriptor;
            captures.append(QJsonObject{{"pair",double(i)},{"raw_file",QString::fromStdString(prefix+".raw565")},
                {"rgb_file",QString::fromStdString(prefix+".rgb640")},{"raw_sha256",QString::fromStdString(rh)},
                {"rgb_sha256",QString::fromStdString(sha256(pair.output.bytes.data(),pair.output.bytes.size()))},
                {"source_bank",int(r.bank)},{"output_bank",int(p.bank)},{"sequence",double(r.sequence)},
                {"generation",double(r.generation)},{"camera",int(r.camera)},
                {"token",QString::number(qulonglong(r.token))},{"source_address",double(r.address)},
                {"output_address",double(p.address)},{"byte_certified",true}});
        });
        std::ostringstream summary; report(summary,result);
        auto json=QJsonDocument::fromJson(QByteArray::fromStdString(summary.str())).object();
        json.insert("model_sha256",QString::fromStdString(runner.model_sha));
        json.insert("runtime_sha256",QString::fromStdString(runner.runtime_sha));
        json.insert("api",QString::fromStdString(runner.api)); json.insert("driver",QString::fromStdString(runner.driver));
        json.insert("input",attr(runner.input_attr()));
        QJsonArray heads; for (const auto& a:runner.output_attrs()) heads.append(attr(a)); json.insert("heads",heads);
        json.insert("warm_pairs",30); json.insert("paired_captures",captures);
        json.insert("metric_contract","Each independent job includes both lease copies/ACKs, byte certification, inventory copy, selected prepare/inference. Hardware conversion is active in baseline too. FPS is observed job completion rate, not unrestricted camera throughput.");
        std::ofstream samples(dir/"samples.csv"); samples.exceptions(std::ios::badbit|std::ios::failbit);
        samples<<"scope,block,index,role,bank,sequence,generation,camera,token,raw_sha256,claim_wait_ms,raw_copy_ack_ms,output_copy_ack_ms,certify_ms,acquire_ms,cpu_prepare_ms,processing_ms,completion_from_capture_ms,input_set_ms,run_ms,get_ms,decode_ms,release_ms,detections\n";
        for (std::size_t i=0;i<result.paired.size();++i) for (int role=0;role<2;++role)
            csv(samples,"paired",i%2,i,role,result.paired[i][role],paired_sha[i]);
        QJsonArray inventory;
        for (std::size_t b=0;b<result.blocks.size();++b) for (std::size_t i=0;i<result.blocks[b].samples.size();++i) {
            const auto& block=result.blocks[b]; const auto& raw=block.raw_inventory[i];
            auto hash=sha256(raw.data(),raw.size());
            csv(samples,"independent",b,i,block.profile==Profile::Baseline ? 0 : 1,block.samples[i],hash);
            inventory.append(QJsonObject{{"block",double(b)},{"index",double(i)},
                {"raw_sha256",QString::fromStdString(hash)}});
        }
        json.insert("timed_inventory",inventory); samples.close();
        require(exit_policy->known_idle(receiver.lease_uncertain()),"未取得已退休 DMA/transport/lease 的安全退出凭据");
        auto document=QJsonDocument(json).toJson(); atomic_json(dir/"report.json",document);
        std::cout<<document.constData(); result_code=result.acceptance ? 0 : 1;
    } catch (const std::exception& e) {
        failure_reason=e.what();
    } catch (...) {
        failure_reason="未知异常：硬件状态不得推定为空闲";
    }
    if (binding.owner && !exit_policy)
        exit_policy=std::make_unique<ExitPolicy>(*binding.owner,activation,generation);
    bool lease_unknown=false;
    try { if (retained_receiver) lease_unknown=retained_receiver->lease_uncertain(); }
    catch (...) { lease_unknown=true; }
    const bool safe=!binding.owner || exit_policy->known_idle(lease_unknown);
    if (safe && failure_reason.empty()) return result_code;
    if (failure_reason.empty()) failure_reason="退出前未获得安全空闲凭据，必须物理恢复";
    auto report_failure=[&] {
        QJsonObject evidence{{"acceptance",false},{"error",QString::fromStdString(failure_reason)},
            {"completed_fps",QJsonValue(QJsonValue::Null)},{"quarantined",!safe},
            {"exit_policy",safe ? "verified_idle" : "retain_until_external_physical_recovery"},
            {"controller_session",QString::fromStdString(activation.controller_session)},
            {"generation",double(generation)},{"lease_uncertain",lease_unknown}};
        if (retained_receiver) {
            const auto& pair=retained_receiver->evidence();
            evidence.insert("raw_complete",pair.raw.complete); evidence.insert("output_complete",pair.output.complete);
            evidence.insert("raw_owned_bytes",double(pair.raw.bytes.size()));
            evidence.insert("output_owned_bytes",double(pair.output.bytes.size()));
            evidence.insert("raw_sequence",double(pair.raw.descriptor.sequence));
            evidence.insert("raw_token",QString::number(qulonglong(pair.raw.descriptor.token)));
        }
        auto failure=QJsonDocument(evidence).toJson(); std::cerr<<failure.constData();
        try { std::filesystem::create_directories(dir); atomic_json(dir/"failure.json",failure); }
        catch (...) { std::cerr<<"原子证据写入失败；仍保持隔离 owner，不能据此退出。\n"; }
    };
    if (safe) { report_failure(); return 1; }
    exit_policy->enter(failure_reason.c_str(),report_failure);
    std::cerr<<"硬件状态不确定：保持 fd/maps/controller lock 和前台进程。禁止自动 ACK/reset/retry/close/unmap/exit。"
               "需要外部授权的物理静止与恢复凭据；SIGKILL/掉电无法由本进程阻止，操作员终止前必须先物理静止。\n";
    while (!exit_policy->hold_once(termination_requested!=0,[] {
        std::cerr<<"已收到终止信号；隔离状态下拒绝退出，仍需外部物理恢复凭据。\n";
    })) std::this_thread::sleep_for(std::chrono::milliseconds(50));
    std::cerr<<"已收到 provider 验证的外部物理恢复凭据，允许 owner 释放并以失败状态退出。\n";
    return 1;
}
