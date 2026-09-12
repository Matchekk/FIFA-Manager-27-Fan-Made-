#pragma once
#include "../src/native/germany_format_plan.h"
inline void RunGermanyFormatTests(std::filesystem::path const& output) {
    if (std::filesystem::exists(output)) throw std::runtime_error("German test output must be new");
    std::filesystem::create_directories(output);
    auto test=[&](std::string const& name,UInt mode) {
        FifamDatabase db;auto country=db.CreateCountry(21);Vector<FifamClub*> clubs;
        for (UInt i=0;i<58;++i) {auto c=db.CreateClub(country);c->mUniqueID=1376257+i;db.AddClubToMap(c);clubs.push_back(c);}
        auto makeLeague=[&](UInt id,UInt count,UInt start) {
            auto p=db.CreateCompetition(FifamCompDbType::League,FifamCompID(id))->AsLeague();
            p->mNumTeams=count;p->mNumRounds=2;p->mFixtures=BelgiumRoundRobin(count);
            for (UInt i=0;i<count;++i)p->mTeams.push_back(FifamClubLink(clubs[start+i]));
            for (UInt i=0;i<(count-1+count%2)*2;++i)p->mFirstSeasonMatchdays.push_back(static_cast<UShort>(20+7*i));
            return p;
        };
        auto third=makeLeague(352387074,20,0),bayern=makeLeague(352387079,18,20),donor=makeLeague(352387086,19,38);
        auto pool=db.CreateCompetition(FifamCompDbType::Pool,FifamCompID(353894403))->AsPool();pool->mNumTeams=mode==4?91:90;
        bayern->mInstructions.PushBack(new FifamInstruction::GET_POOL(pool->mID,72,18));
        pool->mInstructions.PushBack(new FifamInstruction::GET_TAB_X_TO_Y(bayern->mID,2,13));
        auto lower=db.CreateCompetition(FifamCompDbType::Pool,FifamCompID(353894404));
        lower->mInstructions.PushBack(new FifamInstruction::GET_TAB_X_TO_Y(bayern->mID,17,2));
        auto relegation=db.CreateCompetition(FifamCompDbType::Round,FifamCompID(352845829));
        for (UInt pos:{15u,16u})relegation->mInstructions.PushBack(new FifamInstruction::GET_TAB_X_TO_Y(bayern->mID,pos,1));
        auto path=output/(name+".csv");std::ofstream f(path);f<<"competition_id,club_id,team_type\n";
        for (UInt i=0;i<20;++i) {
            UInt idx=i==0?20:i==1?(mode==1?20:mode==3?57:38):i;
            f<<352387074<<','<<clubs[idx]->mUniqueID<<",FIRST\n";
        }
        for (UInt i=20;i<38;++i)f<<352387079<<','<<clubs[i==20?0:i]->mUniqueID<<",FIRST\n";
        f<<352387079<<','<<clubs[1]->mUniqueID<<",FIRST\n";
        for (UInt i=38;i<57;++i)f<<352387086<<','<<clubs[i==38 && mode!=3?57:i]->mUniqueID<<",FIRST\n";
        if (mode!=2)f<<"0,"<<clubs[57]->mUniqueID<<",FIRST\n";
        f.close();bool passed=true;
        try {ApplyGermany2026Membership(db,path);}catch(std::exception const&){passed=false;}
        if (passed!=(mode==0))throw std::runtime_error("German format test differs: "+name);
        if (passed) {
            if (bayern->mNumTeams!=19 || bayern->mTeams.size()!=19 || bayern->mFixtures.size()!=38 || pool->mNumTeams!=91)
                throw std::runtime_error("German format output differs");
            RequireValidLeagueSchedule(*bayern);RequireValidLeagueSchedule(*donor);
        } else if (bayern->mNumTeams!=18 || bayern->mTeams.size()!=18 || third->mTeams[0].mPtr!=clubs[0])
            throw std::runtime_error("Rejected German input mutated baseline");
    };
    test("bayern19-and-boundary",0);test("duplicate-rejected",1);test("missing-boundary-rejected",2);
    test("top-boundary-rejected",3);test("wrong-pool-baseline-rejected",4);
    std::ofstream f(output/"NATIVE_TESTS.json");f<<"{\"status\":\"PASS\",\"tests\":5,\"scope\":\"German19-team schedule, pool consistency, scoped bottom boundary and rejection atomicity\"}\n";
}
