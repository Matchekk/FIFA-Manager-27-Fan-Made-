#pragma once

// Called inside ExportPlayerSemantics while all club references use stable UIDs.
// Club members/captains and country free staff are split out, not discarded:
// their exact links are compared independently of rewritten native person IDs.
inline void ExportWorldSemantics(FifamDatabase& db, std::filesystem::path const& output,
    BCRYPT_ALG_HANDLE algorithm, std::map<FifamPlayer*,std::string> const& playerKeys) {
    std::ofstream clubs(output/"native_world_clubs.csv",std::ios::binary);
    std::ofstream countries(output/"native_world_countries.csv",std::ios::binary);
    std::ofstream links(output/"native_world_person_links.csv",std::ios::binary);
    clubs<<"club_id,country_id,national,serialized_sha256\n";
    countries<<"country_id,serialized_sha256\n";
    links<<"kind,owner_id,slot,person_key\n";
    size_t linkCount=0,errors=0,clubCount=0,countryCount=0;
    std::map<FifamStaff*,std::string> staffKeys;
    std::map<std::string,size_t> keyCounts;
    for (auto const& entry:playerKeys) ++keyCounts["PLAYER:"+entry.second];
    for (auto s:db.mStaffs) {
        std::wstring serialized;
        { FifamWriter writer(&serialized,13,FifamVersion(0x2013,0x12)); s->Write(writer); }
        auto key="STAFF:"+NativeSemanticHash(algorithm,utf8(serialized))+"@"+
            std::to_string(s->mClub?s->mClub->mUniqueID:0);
        staffKeys.emplace(s,key); ++keyCounts[key];
    }
    auto playerLink=[&](char const* kind,UInt owner,size_t slot,FifamPlayer* p) {
        if (!p || !playerKeys.count(p)) { ++errors; return; }
        links<<kind<<','<<owner<<','<<slot<<",PLAYER:"<<playerKeys.at(p)<<'\n'; ++linkCount;
    };
    auto staffLink=[&](char const* kind,UInt owner,size_t slot,FifamStaff* s) {
        if (!s || !staffKeys.count(s)) { ++errors; return; }
        links<<kind<<','<<owner<<','<<slot<<','<<staffKeys.at(s)<<'\n'; ++linkCount;
    };
    auto stripMembers=[](FifamClub& club) {
        club.mPlayers.clear(); club.mStaffs.clear(); club.mCaptains={};
    };
    auto clubRecord=[&](FifamClub* club,bool national) {
        // Copying these value objects does not own/delete their pointer targets.
        auto copy=*club;
        stripMembers(copy);
        std::wstring serialized;
        { FifamWriter writer(&serialized,13,FifamVersion(0x2013,0x12)); copy.Write(writer,1); }
        clubs<<club->mUniqueID<<','<<(club->mCountry?club->mCountry->mId:0)<<','<<national<<','
             <<NativeSemanticHash(algorithm,utf8(serialized))<<'\n'; ++clubCount;
        for (size_t i=0;i<club->mPlayers.size();++i) playerLink("MEMBER_PLAYER",club->mUniqueID,i,club->mPlayers[i]);
        for (size_t i=0;i<club->mStaffs.size();++i) staffLink("MEMBER_STAFF",club->mUniqueID,i,club->mStaffs[i]);
        for (size_t i=0;i<club->mCaptains.size();++i)
            if (club->mCaptains[i]) playerLink("CAPTAIN",club->mUniqueID,i,club->mCaptains[i]);
    };
    for (auto club:db.mClubs) clubRecord(club,false);
    for (auto country:db.mCountries) if (country) clubRecord(&country->mNationalTeam,true);
    for (auto staff:db.mStaffs) if (!staff->mClub)
        staffLink("COUNTRY_FREE_STAFF",staff->mLinkedCountry.ToInt(),0,staff);

    // Country::Write enumerates the database staff pointer set in allocation
    // order. Export that membership above, then omit only this nested content.
    // Swap back even if serialization/allocation throws; original objects and
    // their IDs, writeable state, member ordering and country rules are untouched.
    struct StaffScope {
        FifamDatabase& db; Set<FifamStaff*> saved;
        explicit StaffScope(FifamDatabase& source):db(source) { saved.swap(db.mStaffs); }
        ~StaffScope() { saved.swap(db.mStaffs); }
    } scope(db);
    for (auto country:db.mCountries) if (country) {
        auto copy=*country;
        copy.mClubs.clear(); stripMembers(copy.mNationalTeam);
        copy.mNumWriteableLeagueLevels=16; // FM13 writer's explicit maximum.
        std::wstring serialized;
        {
            FifamWriter writer(&serialized,13,FifamVersion(0x2013,0x12));
            // Countries.sav fields, followed by full native country metadata,
            // referees, CAC pool, 16 league levels and all COUNTRY_MISC rules.
            writer.WriteLineTranslationArray(copy.mName,false);
            writer.WriteLineTranslationArray(copy.mAbbr,false);
            writer.WriteLineTranslationArray(copy.mNameGender);
            writer.WriteLine(copy.mContinent);
            writer.WriteLine(copy.mFirstLanguageForNames);
            writer.WriteLine(copy.mSecondLanguageForNames);
            writer.WriteLine(copy.mTerritory);
            copy.Write(writer);
        }
        countries<<country->mId<<','<<NativeSemanticHash(algorithm,utf8(serialized))<<'\n'; ++countryCount;
    }
    size_t collisions=0;
    for (auto const& entry:keyCounts) if (entry.second>1) collisions+=entry.second;
    clubs.flush(); countries.flush(); links.flush();
    if (!clubs || !countries || !links) throw std::runtime_error("Native world semantic export failed");
    std::ofstream metadata(output/"NATIVE_WORLD_SEMANTICS.json");
    metadata<<"{\"schema\":1,\"clubs\":"<<clubCount<<",\"countries\":"<<countryCount
        <<",\"person_links\":"<<linkCount<<",\"link_errors\":"<<errors<<",\"person_key_collisions\":"<<collisions
        <<",\"scope\":\"Native FM13 club fields including stadiums; country headers, rules, referees and CAC pool; exact ordered club memberships and captain slots; free-staff country membership. Requires separate full player/staff/competition/relationship validation. Global cities, regions, assessment and engine behavior are not covered.\"}\n";
    metadata.flush();
    if (!metadata) throw std::runtime_error("Native world metadata export failed");
}
