#pragma once
#include <bcrypt.h>
#include "FifamStaff.h"

inline std::string NativeSemanticHash(BCRYPT_ALG_HANDLE algorithm,std::string bytes) {
    UCHAR digest[32]{};
    if (bytes.size()>0xFFFFFFFFull || BCryptHash(algorithm,nullptr,0,
        reinterpret_cast<PUCHAR>(bytes.data()),static_cast<ULONG>(bytes.size()),digest,32)<0)
        throw std::runtime_error("Native semantic SHA256 failed");
    constexpr char hex[]="0123456789abcdef";
    std::string hash;
    for (auto b:digest) { hash+=hex[b>>4]; hash+=hex[b&15]; }
    return hash;
}

#include "world_semantics.h"
#include "global_semantics.h"

// Canonical native player serialization with club references normalized to UIDs.
// This covers all persistable player fields, including histories, clauses and
// position biases; it is not a claim about staff, competitions or runtime saves.
inline void ExportPlayerSemantics(FifamDatabase& db, std::filesystem::path const& path) {
    struct Saved { FifamDbWriteable* item; bool writable; UInt id; UInt uid; };
    std::vector<Saved> saved;
    auto normalize=[&](FifamClub* c) {
        auto wasWritable=c->GetIsWriteable();
        // GetWriteableID hides stored IDs when disabled. Temporarily enable the
        // getter so normalization can restore the exact prior internal state.
        c->SetIsWriteable(true);
        saved.push_back({c,wasWritable,c->GetWriteableID(),c->GetWriteableUniqueID()});
        c->SetIsWriteable(true); c->SetWriteableID(c->mUniqueID); c->SetWriteableUniqueID(c->mUniqueID);
    };
    for (auto c:db.mClubs) normalize(c);
    for (auto c:db.mCountries) if (c) normalize(&c->mNationalTeam);
    BCRYPT_ALG_HANDLE algorithm=nullptr;
    if (BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)
        throw std::runtime_error("Cannot initialize semantic SHA256");
    try {
        std::ofstream file(path,std::ios::binary);
        if (!file) throw std::runtime_error("Cannot open native semantic export");
        file<<"fm_id,fifa_id,dob,name,club_id,serialized_sha256\n";
        std::vector<FifamPlayer*> ordered(db.mPlayers.begin(),db.mPlayers.end());
        std::map<FifamPlayer*,std::string> personKeys;
        std::map<std::string,size_t> keyCounts;
        std::sort(ordered.begin(),ordered.end(),[](auto a,auto b){ return a->mID<b->mID; });
        for (auto p:ordered) {
            std::wstring serialized;
            { FifamWriter writer(&serialized,13,FifamVersion(0x2013,0x12)); p->Write(writer); }
            auto hash=NativeSemanticHash(algorithm,utf8(serialized));
            auto key=hash+"@"+std::to_string(p->mClub?p->mClub->mUniqueID:0);
            personKeys.emplace(p,key); ++keyCounts[key];
            file<<p->mID<<','<<p->mFifaID<<','<<p->mBirthday.ToStringA()<<','<<csv(p->GetName())<<','
                <<(p->mClub?p->mClub->mUniqueID:0)<<','<<hash<<'\n';
        }
        file.flush();
        if (!file) throw std::runtime_error("Native semantic export write failed");
        // Extend coverage without claiming a full world-database gate. Native
        // staff and competition serializers use the same normalized club links.
        std::ofstream staffFile(path.parent_path()/"native_staff_semantics.csv",std::ios::binary);
        staffFile<<"fm_id,dob,name,club_id,serialized_sha256\n";
        for (auto s:db.mStaffs) {
            std::wstring serialized;
            { FifamWriter writer(&serialized,13,FifamVersion(0x2013,0x12)); s->Write(writer); }
            staffFile<<s->mID<<','<<s->mBirthday.ToStringA()<<','<<csv(s->GetName())<<','
                <<(s->mClub?s->mClub->mUniqueID:0)<<','<<NativeSemanticHash(algorithm,utf8(serialized))<<'\n';
        }
        std::ofstream compFile(path.parent_path()/"native_competition_semantics.csv",std::ios::binary);
        compFile<<"competition_id,serialized_sha256\n";
        for (auto const& entry:db.mCompMap) {
            auto comp=entry.second;
            FifamNation nation;
            if (comp->mID.mRegion.ToInt()>0 && comp->mID.mRegion.ToInt()<=FifamDatabase::NUM_COUNTRIES)
                nation.SetFromInt(comp->mID.mRegion.ToInt());
            std::wstring serialized;
            { FifamWriter writer(&serialized,13,FifamVersion(0x2013,0x12)); db.WriteCompetition(writer,comp,nation); }
            compFile<<comp->mID.ToInt()<<','<<NativeSemanticHash(algorithm,utf8(serialized))<<'\n';
        }
        std::ofstream graphFile(path.parent_path()/"native_player_relations.csv",std::ios::binary);
        graphFile<<"relation,from_key,to_key\n";
        size_t graphRows=0,relationErrors=0,keyCollisions=0;
        for (auto const& entry:keyCounts) if (entry.second>1) keyCollisions+=entry.second;
        for (auto p:ordered) {
            auto links=[&](auto const& related,char const* kind) {
                for (auto other:related) {
                    if (!personKeys.count(other) || other==p) { ++relationErrors; continue; }
                    graphFile<<kind<<','<<personKeys.at(p)<<','<<personKeys.at(other)<<'\n'; ++graphRows;
                }
            };
            links(p->mBrothers,"BROTHER"); links(p->mCousins,"COUSIN");
        }
        staffFile.flush(); compFile.flush(); graphFile.flush();
        if (!staffFile || !compFile || !graphFile) throw std::runtime_error("Extended native semantic export failed");
        std::ofstream metadata(path.parent_path()/"NATIVE_EXTENDED_SEMANTICS.json");
        metadata<<"{\"staffs\":"<<db.mStaffs.size()<<",\"competitions\":"<<db.mCompMap.size()
                <<",\"relation_rows\":"<<graphRows<<",\"relation_errors\":"<<relationErrors
                <<",\"player_key_collisions\":"<<keyCollisions
                <<",\"scope\":\"Staff and competition serialization; player brother/cousin graph. Club/country/rules/stadium completeness is NOT proven.\"}\n";
        metadata.flush();
        if (!metadata) throw std::runtime_error("Extended native semantic metadata failed");
        ExportWorldSemantics(db,path.parent_path(),algorithm,personKeys);
        ExportGlobalSemantics(db,path.parent_path(),algorithm);
    } catch (...) {
        BCryptCloseAlgorithmProvider(algorithm,0);
        for (auto const& s:saved) { s.item->SetIsWriteable(s.writable); s.item->SetWriteableID(s.id); s.item->SetWriteableUniqueID(s.uid); }
        throw;
    }
    BCryptCloseAlgorithmProvider(algorithm,0);
    for (auto const& s:saved) { s.item->SetIsWriteable(s.writable); s.item->SetWriteableID(s.id); s.item->SetWriteableUniqueID(s.uid); }
}
