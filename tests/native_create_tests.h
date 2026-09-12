#pragma once
#include "../src/native/create_player_plan.h"

inline void RunCreatePlayerTests(std::filesystem::path const& output) {
    if (std::filesystem::exists(output)) throw std::runtime_error("Creation test output must be new");
    std::filesystem::create_directories(output);
    const std::string header="fm_id,player_tm_id,fifa_id,first_name,last_name,pseudonym,dob,nationality1,nationality2,club_id,joined,contract_until,shirt_number,team_type,position,rating_seed,status,source,source_sha256,snapshot_date\n";
    auto run=[&](std::string const& name,std::string id,std::string tm,std::string seed,bool succeeds) {
        FifamDatabase db; auto country=db.CreateCountry(14); auto club=db.CreateClub(country);
        club->mUniqueID=917505; db.AddClubToMap(club);
        if (name=="duplicate-tm") { auto existing=db.CreatePlayer(club,1); existing->mTmDeID=555; }
        auto path=output/(name+".csv");
        { std::ofstream file(path); file<<header<<id<<','<<tm<<",0,New,Player,,2004-01-02,14,0,917505,2026-07-01,2029-06-30,27,FIRST,CM,"
            <<seed<<",CONFIRMED,https://example.com/player,"<<std::string(64,'a')<<",2026-09-12\n"; }
        bool passed=false; try { passed=ApplyCreatePlayerPlan(db,path).players==1; }
        catch (std::runtime_error const&) { if (succeeds) throw; }
        if (succeeds) {
            auto player=db.mPersonsMap.at(static_cast<UInt>(std::stoul(id)))->AsPlayer();
            if (!passed || !player || player->mClub!=club || player->mTmDeID!=std::stoul(tm) || player->mFifaID ||
                player->GetName()!=L"New Player" || player->mNationality[0].ToInt()!=14 ||
                player->mMainPosition.ToInt()!=FifamPlayerPosition::CM || player->mAttributes.Pace!=45 ||
                player->mContract.mValidUntil!=FifamDate(30,6,2029) || player->mShirtNumberFirstTeam!=27)
                throw std::runtime_error("Created player semantics differ");
        } else if (passed || (name!="duplicate-tm" && !db.mPlayers.empty()) ||
                   (name=="duplicate-tm" && db.mPlayers.size()!=1))
            throw std::runtime_error("Rejected creation mutated database");
    };
    run("create","500000","555","45",true);
    run("duplicate-tm","500001","555","45",false);
    run("rating-out-of-bounds","500002","556","61",false);
    std::ofstream report(output/"NATIVE_CREATE_TESTS.json");
    report<<"{\"status\":\"PASS\",\"tests\":3,\"scope\":\"guarded player creation identity, source fields and bounded provisional rating\"}\n";
}
