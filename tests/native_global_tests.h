#pragma once

inline void RunNativeGlobalTests(std::filesystem::path const& output) {
    FifamDatabase db;
    auto country=db.CreateCountry(14);
    auto& city=db.mCities[10]; city.id=10; city.countryId=14; city.latitude=51.5f;
    auto& region=db.mRegions[20]; region.id=20; region.countryId=14; region.longitude=-1.25f;
    auto& appearance=db.mAppearanceDefs.mDefs[1];
    appearance.unknown=0; appearance.mHeight=180; appearance.mWeight=75;
    appearance.mParameters[0]={{1,50},{2,50}};
    auto capture=[&](char const* name) {
        auto dir=output/name; std::filesystem::create_directories(dir);
        ExportPlayerSemantics(db,dir/"native_player_semantics.csv");
        std::ifstream file(dir/"native_global_semantics.csv",std::ios::binary);
        return std::string(std::istreambuf_iterator<char>(file),std::istreambuf_iterator<char>());
    };
    auto before=capture("global-original");
    ++db.mRules.mNumSubsInFriendlyMatches;
    auto rules=capture("global-rules");
    if (before==rules) throw std::runtime_error("Global rules mutation not detected");
    ++city.population;
    auto cities=capture("global-cities");
    if (rules==cities) throw std::runtime_error("City mutation not detected");
    region.names[CustomLanguages::TRANSLATIONLANGUAGE_ENG]=L"Changed region";
    auto regions=capture("global-regions");
    if (cities==regions) throw std::runtime_error("Region mutation not detected");
    appearance.mParameters[0][0].second=25;
    auto definitions=capture("global-appearance");
    if (regions==definitions) throw std::runtime_error("Appearance distribution mutation not detected");
    ++country->mAssessmentData[0];
    if (definitions==capture("global-assessment")) throw std::runtime_error("Assessment mutation not detected");
    std::ofstream report(output/"NATIVE_TESTS.json");
    report<<"{\"status\":\"PASS\",\"tests\":55,\"scope\":\"50 staging, loan, world, semantic and support cases; 5 global cases: international rules, cities, regions, appearance distributions, country assessment\"}\n";
}
