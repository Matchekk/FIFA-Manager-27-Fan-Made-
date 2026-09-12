#pragma once
#include "../src/native/belgium_format_plan.h"

inline void RunBelgiumFormatTests(std::filesystem::path const& output) {
    if (std::filesystem::exists(output)) throw std::runtime_error("Belgium test output must be new");
    std::filesystem::create_directories(output);
    auto test=[&](std::string const& name,bool duplicate,bool missing,bool reserveTop,UInt boundaryMode=0) {
        FifamDatabase db; auto country=db.CreateCountry(7);
        Vector<FifamClub*> clubs;
        for (UInt i=0;i<(boundaryMode?52u:33u);++i) {
            auto club=db.CreateClub(country); club->mUniqueID=458753+i; db.AddClubToMap(club); clubs.push_back(club);
        }
        auto makeLeague=[&](UInt id,UInt count,UInt start) {
            auto p=db.CreateCompetition(FifamCompDbType::League,FifamCompID(id))->AsLeague();
            p->mNumTeams=count;p->mNumRounds=2;p->mFixtures=BelgiumRoundRobin(count);
            for (UInt i=0;i<count;++i) p->mTeams.push_back(FifamClubLink(clubs[start+i]));
            for (UInt i=0;i<(count-1+count%2)*2;++i) p->mFirstSeasonMatchdays.push_back(static_cast<UShort>(30+7*i));
            return p;
        };
        auto top=makeLeague(117506048,16,0),second=makeLeague(117506049,17,16);
        if (boundaryMode) makeLeague(117506052,18,33);
        auto pool0=db.CreateCompetition(FifamCompDbType::Pool,FifamCompID(119013376))->AsPool();pool0->mNumTeams=16;
        auto pool1=db.CreateCompetition(FifamCompDbType::Pool,FifamCompID(119013377))->AsPool();pool1->mNumTeams=17;
        auto pool2=db.CreateCompetition(FifamCompDbType::Pool,FifamCompID(119013378))->AsPool();
        pool2->mInstructions.PushBack(new FifamInstruction::GET_TAB_X_TO_Y(second->mID,16,2));
        for (UInt id:{117964800u,117964801u,117964802u}) {
            auto p=db.CreateCompetition(FifamCompDbType::Round,FifamCompID(id));p->mNumTeams=id==117964800?4:2;
        }
        auto path=output/(name+".csv");std::ofstream file(path);
        file<<"competition_id,club_id,team_type\n";
        for (UInt i=0;i<33;++i) {
            if (missing && i==32) continue;
            file<<(i<18?117506048:117506049)<<','<<(duplicate && i==32?458753:boundaryMode==4 && i==0?458804:458753+i)<<','
                <<(reserveTop && i==0?"RESERVE":"FIRST")<<'\n';
        }
        if (boundaryMode) {
            for (UInt i=33;i<51;++i)
                file<<117506052<<','<<(i==33 && boundaryMode!=4?458804:458753+i)<<",FIRST\n";
            if (boundaryMode!=2) file<<"0,"<<(boundaryMode==4?458753:458786)<<",FIRST\n";
            file<<"0,458804,FIRST\n";
            if (boundaryMode==3) file<<"0,458753,FIRST\n";
        }
        file.close();bool passed=true;
        try { ApplyBelgium2026Format(db,path); } catch(std::exception const&) { passed=false; }
        bool expected=!duplicate&&!missing&&!reserveTop&&(boundaryMode<2);
        if (passed!=expected) throw std::runtime_error("Belgium test result differs: "+name);
        if (!passed) {
            if (top->mNumTeams!=16 || second->mNumTeams!=17 || top->mTeams.size()!=16 || !db.GetCompetition(FifamCompID(117964802)))
                throw std::runtime_error("Belgium rejected input mutated baseline");
        } else {
            if (top->mTeams.size()!=18 || second->mTeams.size()!=15 || pool0->mNumTeams!=18 || pool1->mNumTeams!=15 ||
                db.GetCompetition(FifamCompID(117964802)) || top->mFixtures.size()!=34 || second->mFixtures.size()!=30)
                throw std::runtime_error("Belgium format topology differs");
            RequireValidLeagueSchedule(*top);RequireValidLeagueSchedule(*second);
        }
    };
    test("format18-15",false,false,false);
    test("duplicate-rejected",true,false,false);
    test("missing-rejected",false,true,false);
    test("reserve-top-rejected",false,false,true);
    test("documented-bottom-boundary",false,false,false,1);
    test("undeclared-bottom-exit-rejected",false,false,false,2);
    test("unused-boundary-rejected",false,false,false,3);
    test("top-boundary-rejected",false,false,false,4);
    std::ofstream report(output/"NATIVE_TESTS.json");
    report<<"{\"status\":\"PASS\",\"tests\":8,\"scope\":\"Belgium18/15 fixtures, conservation, guarded bottom boundary, reserve exclusion and atomic input rejection\"}\n";
}
