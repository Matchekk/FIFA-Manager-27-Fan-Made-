#pragma once

// The upstream brother writer assumes every connected group is a clique.
// Half-sibling graphs need individual edges; the reader supports pair rows.
inline void WriteExactPlayerRelations(FifamDatabase& db,std::filesystem::path const& path) {
    Map<String,Vector<FifamPlayer*>> byName;
    for (auto p:db.mPlayers) byName[p->GetStringUniqueId(13,false)].push_back(p);
    auto checkedId=[&](FifamPlayer* p) {
        if (!db.mPlayers.count(p) || !p->GetWriteableID() || p->mWriteableStringID.empty())
            throw std::runtime_error("Relation endpoint is not persistable");
        auto const& id=p->mWriteableStringID;
        auto const& candidates=byName.at(p->GetStringUniqueId(13,false));
        if (candidates.size()==1) {
            if (id!=p->GetStringUniqueId(13,false)) throw std::runtime_error("Unexpected unique relation identifier");
        } else {
            size_t matches=0;
            for (auto candidate:candidates) if (p->mEmpicsId && candidate->mEmpicsId==p->mEmpicsId) ++matches;
            if (matches!=1 || id!=p->GetStringUniqueId(13,false)+L"-"+std::to_wstring(p->mEmpicsId))
                throw std::runtime_error("Ambiguous relation identifier");
        }
        return id;
    };
    std::set<std::tuple<String,String,String>> edges;
    for (auto p:db.mPlayers) {
        auto collect=[&](auto const& related,String const& kind) {
            for (auto other:related) {
                if (!db.mPlayers.count(other) || other==p) throw std::runtime_error("Invalid relation endpoint");
                auto const& reverse=kind==L"BROTHER"?other->mBrothers:other->mCousins;
                if (!reverse.count(p)) throw std::runtime_error("Asymmetric relationship cannot be written without mutation");
                auto first=checkedId(p),second=checkedId(other);
                if (second<first) std::swap(first,second);
                edges.emplace(kind,first,second);
            }
        };
        collect(p->mBrothers,L"BROTHER"); collect(p->mCousins,L"COUSIN");
    }
    // Validate the entire graph before replacing the staging-only native output.
    FifamWriter writer(path,13,FifamVersion(),true);
    if (!writer.Available()) throw std::runtime_error("Cannot write exact player relations");
    writer.WriteLine(L"#Relation, Player1, Player2");
    for (auto const& edge:edges)
        writer.WriteLine(std::get<0>(edge)+L",\t"+std::get<1>(edge)+L",\t"+std::get<2>(edge));
}

// Preserve unedited external scripts (including mod-specific sections unknown
// to the generic writer), historic data and name tables omitted by that writer.
// All copies stay in the already isolated staging tree and are hash recorded.
inline void PreserveNativeSupport(std::filesystem::path const& input,std::filesystem::path const& output) {
    namespace fs=std::filesystem;
    BCRYPT_ALG_HANDLE algorithm=nullptr;
    if (BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)
        throw std::runtime_error("Cannot initialize support-file hashing");
    try {
        std::ofstream manifest(output/"native_support_files.csv",std::ios::binary);
        manifest<<"relative_path,sha256\n";
        auto copy=[&](fs::path const& source,fs::path const& destination) {
            if (fs::is_symlink(source) || !fs::is_regular_file(source)) throw std::runtime_error("Unsupported support-file entry");
            if (fs::exists(destination)) throw std::runtime_error("Support copy would overwrite generated data");
            fs::create_directories(destination.parent_path());
            fs::copy_file(source,destination);
            auto bytes=[](fs::path const& file) {
                std::ifstream stream(file,std::ios::binary);
                if (!stream) throw std::runtime_error("Cannot read support file");
                return std::string(std::istreambuf_iterator<char>(stream),std::istreambuf_iterator<char>());
            };
            auto digest=NativeSemanticHash(algorithm,bytes(source));
            if (digest!=NativeSemanticHash(algorithm,bytes(destination))) throw std::runtime_error("Support copy hash mismatch");
            manifest<<csv(fs::relative(destination,output).generic_wstring())<<','<<digest<<'\n';
        };
        for (auto const* folder:{L"script",L"fmdata/historic"}) {
            auto source=input.parent_path()/folder;
            if (!fs::exists(source)) continue;
            if (fs::is_symlink(source)) throw std::runtime_error("Support directory cannot be a symlink");
            for (auto const& entry:fs::recursive_directory_iterator(source)) {
                if (entry.is_symlink()) throw std::runtime_error("Support tree cannot contain symlinks");
                if (entry.is_regular_file()) copy(entry.path(),output/folder/fs::relative(entry.path(),source));
            }
        }
        // UCP/editor auxiliary files are not represented by FifamDatabase.
        // Preserve their original bytes; never copy stale compiled Master.dat.
        for (auto const* name:{L"MaleNames.txt",L"FemaleNames.txt",L"Surnames.txt",
            L"AssessmentAFC.sav",L"AssessmentCAF.sav",L"CountryNames.txt",
            L"picture.tga",L"PriorityClubs.txt",L"TownDataUniques.txt"})
            if (fs::exists(input/name)) copy(input/name,output/L"database"/name);
        manifest.flush();
        if (!manifest) throw std::runtime_error("Support manifest write failed");
    } catch (...) { BCryptCloseAlgorithmProvider(algorithm,0); throw; }
    BCryptCloseAlgorithmProvider(algorithm,0);
}
