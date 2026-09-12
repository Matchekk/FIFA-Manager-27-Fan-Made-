#pragma once

// Remaining global FM13 objects. Uses native Write where available and the
// exact persistable field set for table/appearance serializers without streams.
inline void ExportGlobalSemantics(FifamDatabase& db,std::filesystem::path const& output,BCRYPT_ALG_HANDLE algorithm) {
    std::ofstream file(output/"native_global_semantics.csv",std::ios::binary);
    file<<"kind,object_id,serialized_sha256\n";
    size_t count=0;
    auto record=[&](char const* kind,auto id,auto serialize) {
        std::wstring serialized;
        { FifamWriter writer(&serialized,13,FifamVersion(0x2013,0x12)); serialize(writer); }
        file<<kind<<','<<id<<','<<NativeSemanticHash(algorithm,utf8(serialized))<<'\n'; ++count;
    };
    record("RULES",0,[&](FifamWriter& w) { db.mRules.Write(w); });
    for (auto country:db.mCountries) if (country)
        record("ASSESSMENT",country->mId,[&](FifamWriter& w) { w.WriteLineArray(country->mAssessmentData); });
    for (auto const& entry:db.mCities) {
        auto const& c=entry.second;
        record("CITY",entry.first,[&](FifamWriter& w) {
            w.WriteLine(c.id,c.countryId,c.population,c.weight,std::to_wstring(c.latitude),std::to_wstring(c.longitude),
                c.altitude,c.attraction,c.language,c.climate,c.regionId,c.wikidataId);
            w.WriteLine(c.countryName); w.WriteLine(c.languageName); w.WriteLineArray(c.names);
        });
    }
    for (auto const& entry:db.mRegions) {
        auto const& r=entry.second;
        record("REGION",entry.first,[&](FifamWriter& w) {
            w.WriteLine(r.id,r.countryId,r.population,std::to_wstring(r.latitude),std::to_wstring(r.longitude),r.climate,r.wikidataId);
            w.WriteLine(r.countryName); w.WriteLineArray(r.names);
        });
    }
    for (auto const& entry:db.mAppearanceDefs.mDefs) {
        auto const& def=entry.second;
        record("APPEARANCE",entry.first,[&](FifamWriter& w) {
            w.WriteLine(def.mNames.size());
            for (auto const& name:def.mNames) { w.WriteLine(name.first); w.WriteLine(name.second); }
            w.WriteLine(def.unknown,def.mHeight,def.mWeight,def.mParameters.size());
            for (auto const& values:def.mParameters) {
                w.WriteLine(values.size());
                for (auto const& value:values) w.WriteLine(value.first,value.second);
            }
        });
    }
    for (size_t i=0;i<db.mCupTemplates.size();++i)
        record("CUP_TEMPLATE",i,[&](FifamWriter& w) { db.mCupTemplates[i]->Write(w,&db); });
    file.flush();
    if (!file) throw std::runtime_error("Global native semantic export failed");
    std::ofstream metadata(output/"NATIVE_GLOBAL_SEMANTICS.json");
    metadata<<"{\"schema\":1,\"records\":"<<count<<",\"cities\":"<<db.mCities.size()
        <<",\"regions\":"<<db.mRegions.size()<<",\"appearance_definitions\":"<<db.mAppearanceDefs.mDefs.size()
        <<",\"cup_templates\":"<<db.mCupTemplates.size()<<",\"legacy_standalone_stadiums\":"<<db.mStadiums.size()
        <<",\"legacy_sponsors\":"<<db.mSponsors.size()
        <<",\"scope\":\"Native global rules, country assessment values, all persistable city/region and appearance-definition fields, cup templates. Name/history/external mod files require independent byte-exact support validation. Does not prove engine behavior.\"}\n";
    metadata.flush();
    if (!metadata) throw std::runtime_error("Global native metadata export failed");
}
