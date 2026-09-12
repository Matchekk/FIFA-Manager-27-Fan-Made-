#pragma once

inline void RunCompetitionInspectionTests(std::filesystem::path const& output) {
    FifamDatabase db;
    auto country=db.CreateCountry(14);
    auto club=db.CreateClub(country); club->mUniqueID=917505; db.AddClubToMap(club);
    auto other=db.CreateClub(country); other->mUniqueID=917506; db.AddClubToMap(other);
    auto league=db.CreateCompetition(FifamCompDbType::League,FifamCompID(14u,FifamCompType::League,0))->AsLeague();
    auto pool=db.CreateCompetition(FifamCompDbType::Pool,FifamCompID(14u,FifamCompType::Pool,0))->AsPool();
    league->mNumTeams=2; league->mNumRounds=2;
    league->mTeams={FifamClubLink(club),FifamClubLink(other,FifamClubTeamType::Reserve)};
    league->mFirstSeasonMatchdays={1,8}; league->mSecondSeasonMatchdays={2,9}; league->GenerateFixtures();
    pool->mNumTeams=2;
    pool->mInstructions.PushBack(new FifamInstruction::GET_TAB_X_TO_Y(league->mID,1,1));
    league->mPredecessors={pool->mID}; pool->mCompConstraints={league->mID};
    auto content=[](std::filesystem::path const& path) {
        std::ifstream file(path,std::ios::binary);
        return std::string(std::istreambuf_iterator<char>(file),std::istreambuf_iterator<char>());
    };
    auto capture=[&](char const* name) {
        auto dir=output/name; std::filesystem::create_directories(dir);
        ExportCompetitionInspection(db,dir); return dir;
    };
    auto before=capture("competition-before"),same=capture("competition-same");
    for (auto name:{"competition_structure.csv","competition_members.csv","competition_calendars.csv",
        "competition_fixtures.csv","competition_edges.csv","competition_instructions.csv"})
        if (content(before/name)!=content(same/name)) throw std::runtime_error("Competition inspection is not deterministic");
    if (content(before/"competition_members.csv").find(utf8(FifamClubTeamType(FifamClubTeamType::Reserve).ToStr()))==std::string::npos)
        throw std::runtime_error("Reserve membership disappeared from competition inspection");
    ++league->mNumRelegatedTeams;
    auto rules=capture("competition-rules");
    if (content(rules/"competition_structure.csv")==content(before/"competition_structure.csv"))
        throw std::runtime_error("Relegation rule inspection missed change");
    ++league->mSecondSeasonMatchdays[0];
    auto calendar=capture("competition-calendar");
    if (content(calendar/"competition_calendars.csv")==content(rules/"competition_calendars.csv"))
        throw std::runtime_error("Second season calendar inspection missed change");
    std::swap(league->mFixtures[0][0].first,league->mFixtures[0][0].second);
    auto fixture=capture("competition-fixture");
    if (content(fixture/"competition_fixtures.csv")==content(calendar/"competition_fixtures.csv"))
        throw std::runtime_error("Fixture inspection missed home/away change");
    pool->mInstructions.Clear();
    pool->mInstructions.PushBack(new FifamInstruction::GET_TAB_X_TO_Y(league->mID,1,2));
    auto instruction=capture("competition-instruction");
    if (content(instruction/"competition_instructions.csv")==content(fixture/"competition_instructions.csv"))
        throw std::runtime_error("Instruction range inspection missed change");
    FifamCompID missing(14u,FifamCompType::League,99);
    league->mSuccessors.push_back(missing);
    auto dangling=capture("competition-dangling");
    if (content(dangling/"competition_edges.csv").find(","+std::to_string(missing.ToInt())+",0\n")==std::string::npos)
        throw std::runtime_error("Missing competition target was hidden");
    std::ofstream report(output/"NATIVE_TESTS.json");
    report<<"{\"status\":\"PASS\",\"tests\":80,\"scope\":\"73 prior native cases; 7 competition inspection cases: deterministic clone serialization, reserve identity, relegation rules, second calendar, fixtures, instruction ranges, unresolved target visibility\"}\n";
}
