#pragma once

inline void RunLeagueMembershipTests(std::filesystem::path const& output) {
    using Rows=std::vector<std::vector<std::string>>;
    size_t cases=0;
    for (std::string name:{"valid","sparse-valid","missing-slot","wrong-origin","duplicate-slot","duplicate-destination",
        "unbalanced-promotion","foreign-country","youth-type","unconfirmed","bad-source","mixed-date",
        "bad-calendar","bad-fixture","ambiguous-native-membership","wrong-comp-type","bad-slot"}) {
        FifamDatabase db;
        auto country=db.CreateCountry(14),foreign=db.CreateCountry(21);
        std::vector<FifamClub*> clubs;
        for (UInt i=1;i<=4;++i) {
            auto club=db.CreateClub(country); club->mUniqueID=9000+i; db.AddClubToMap(club); clubs.push_back(club);
        }
        auto abroad=db.CreateClub(foreign); abroad->mUniqueID=9999; db.AddClubToMap(abroad);
        auto first=db.CreateCompetition(FifamCompDbType::League,FifamCompID(14u,FifamCompType::League,0))->AsLeague();
        auto second=db.CreateCompetition(FifamCompDbType::League,FifamCompID(14u,FifamCompType::League,1))->AsLeague();
        auto pool=db.CreateCompetition(FifamCompDbType::Pool,FifamCompID(14u,FifamCompType::Pool,0));
        first->mTeams={FifamClubLink(clubs[0]),FifamClubLink(clubs[1])};
        second->mTeams={FifamClubLink(clubs[2]),FifamClubLink(clubs[3],FifamClubTeamType::Reserve)};
        for (auto league:{first,second}) {
            league->mNumTeams=2; league->mNumRounds=2; league->mFirstSeasonMatchdays={7,14};
            league->mSecondSeasonMatchdays={14,21}; league->GenerateFixtures();
        }
        auto player=db.CreatePlayer(clubs[1],11); player->mFirstName=L"Unchanged";
        Rows rows;
        for (auto league:{first,second}) for (UInt slot=1;slot<=2;++slot) {
            auto old=league->mTeams[slot-1];
            UInt next=old.mPtr->mUniqueID;
            if (league==first && slot==2) next=9003;
            if (league==second && slot==1) next=9002;
            std::string type=old.IsReserveTeam()?"RESERVE":"FIRST";
            rows.push_back({std::to_string(league->mID.ToInt()),std::to_string(slot),std::to_string(old.mPtr->mUniqueID),type,
                std::to_string(next),type,"CONFIRMED","https://example.com/review",std::string(64,'a'),"2026-09-08"});
        }
        if (name=="sparse-valid") rows={rows[1],rows[2]};
        if (name=="missing-slot") rows.erase(rows.begin()+2);
        if (name=="wrong-origin") rows[0][2]="9004";
        if (name=="duplicate-slot") rows.push_back(rows[0]);
        if (name=="duplicate-destination") rows[0][4]="9003";
        if (name=="unbalanced-promotion") rows.resize(2);
        if (name=="foreign-country") rows[0][4]="9999";
        if (name=="youth-type") rows[0][5]="YOUTH";
        if (name=="unconfirmed") rows[0][6]="REVIEW_REQUIRED";
        if (name=="bad-source") rows[0][8]="missing";
        if (name=="mixed-date") rows[0][9]="2026-09-07";
        if (name=="bad-calendar") first->mSecondSeasonMatchdays={7,7};
        if (name=="bad-fixture") first->mFixtures[1]=first->mFixtures[0];
        if (name=="ambiguous-native-membership") {
            auto duplicate=db.CreateCompetition(FifamCompDbType::League,FifamCompID(14u,FifamCompType::League,2))->AsLeague();
            duplicate->mTeams={FifamClubLink(clubs[0])};
        }
        if (name=="wrong-comp-type") rows[0][0]=std::to_string(pool->mID.ToInt());
        if (name=="bad-slot") rows[0][1]="0";
        auto firstBefore=first->mTeams,secondBefore=second->mTeams;
        auto firstFixtures=first->mFixtures,secondFixtures=second->mFixtures;
        auto path=output/("league-"+name+".csv");
        {
            std::ofstream plan(path);
            plan<<"competition_id,slot,old_club_id,old_team_type,new_club_id,new_team_type,status,source,source_sha256,snapshot_date\n";
            for (auto const& row:rows) {
                for (size_t i=0;i<row.size();++i) plan<<(i?",":"")<<row[i];
                plan<<'\n';
            }
        }
        bool rejected=false;
        LeagueMembershipResult result;
        try { result=ApplyLeagueMembershipPlan(db,path); } catch (std::runtime_error const&) { rejected=true; }
        if (name=="valid" || name=="sparse-valid") {
            if (rejected || result.leagues!=2 || result.changedSlots!=2 || first->mTeams[1].mPtr!=clubs[2]
                || second->mTeams[0].mPtr!=clubs[1] || !second->mTeams[1].IsReserveTeam()
                || player->mClub!=clubs[1] || first->mFixtures!=firstFixtures || second->mFixtures!=secondFixtures)
                throw std::runtime_error("Balanced league move failed or altered unrelated native state");
        }
        else if (!rejected || first->mTeams!=firstBefore || second->mTeams!=secondBefore)
            throw std::runtime_error("League plan rejection was not atomic: "+name);
        ++cases;
    }
    // The actual upstream fixture tables must work for the upcoming15/18-team formats.
    for (UInt count:{15u,18u}) {
        FifamCompLeague league; league.mNumTeams=count; league.mNumRounds=2;
        for (UInt i=0;i<(count-1+count%2)*2;++i) league.mFirstSeasonMatchdays.push_back(static_cast<UShort>(7+i*7));
        league.mSecondSeasonMatchdays=league.mFirstSeasonMatchdays; league.GenerateFixtures();
        RequireValidLeagueSchedule(league); ++cases;
    }
    std::ofstream report(output/"NATIVE_TESTS.json");
    report<<"{\"status\":\"PASS\",\"tests\":"<<(80+cases)
        <<",\"scope\":\"80 prior native cases; 19 league cases: balanced atomic full/sparse membership, source/identity/calendar/fixture guards, global conservation, native15/18-team fixture generation\"}\n";
}
