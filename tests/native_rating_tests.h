#pragma once

inline void RunRatingTests(std::filesystem::path const& output) {
    size_t cases=0;
    for (std::string const name:{"valid","preview","wrong-player","wrong-fifa","wrong-dob","wrong-club",
        "stale-hash","bad-level","missing-level","out-of-range","unconfirmed","source-unbound",
        "mixed-date","duplicate","late-rejection","no-change","wrong-schema","empty"}) {
        FifamDatabase db;
        auto country=db.CreateCountry(14);
        auto club=db.CreateClub(country); club->mUniqueID=917505; db.AddClubToMap(club);
        auto first=db.CreatePlayer(club,1),second=db.CreatePlayer(club,2);
        for (auto player:{first,second}) {
            player->mFifaID=100+player->mID; player->mBirthday=FifamDate(2,1,2000);
            player->mFirstName=L"Identity"; player->mMainPosition=FifamPlayerPosition::ST;
            player->mPositionBias[17]=100; player->mGeneralExperience=9; player->mTalent=7; player->mPotential=70;
            for (auto const& field:RatingAttributes13()) player->mAttributes.*(field.value)=50;
        }
        std::vector<std::vector<std::string>> rows;
        std::string beforeFirst,beforeSecond;
        {
            RatingHashScope hashes(db);
            beforeFirst=hashes.hash(*first); beforeSecond=hashes.hash(*second);
            for (auto player:{first,second}) {
                std::vector<std::string> row={std::to_string(player->mID),std::to_string(player->mFifaID),
                    "2000-01-02","917505",hashes.hash(*player),""};
                RatingAttributeRestore restore(*player);
                for (auto const& field:RatingAttributes13()) {
                    player->mAttributes.*(field.value)=65; row.push_back("65");
                }
                row[5]=std::to_string(FifamPlayerLevel::GetPlayerLevel13(player,player->mMainPosition,player->mPlayingStyle));
                for (auto value:{"CONFIRMED","https://example.com/rating","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","2026-09-08"})
                    row.push_back(value);
                rows.push_back(row);
            }
        }
        auto header=RatingPlanHeader();
        size_t evidence=6+RatingAttributes13().size();
        if (name=="preview" || name=="missing-level") rows[0][5]="";
        if (name=="wrong-player") rows[0][0]="99";
        if (name=="wrong-fifa") rows[0][1]="999";
        if (name=="wrong-dob") rows[0][2]="2000-01-03";
        if (name=="wrong-club") rows[0][3]="0";
        if (name=="stale-hash") first->mTalent=8;
        if (name=="bad-level") rows[0][5]="99";
        if (name=="out-of-range") rows[0][6]="100";
        if (name=="unconfirmed") rows[0][evidence]="REVIEW";
        if (name=="source-unbound") rows[0][evidence+2]="";
        if (name=="mixed-date") rows[1][evidence+3]="2026-09-07";
        if (name=="duplicate") rows[1]=rows[0];
        if (name=="late-rejection") rows[1][6]="256";
        if (name=="no-change") for (size_t i=6;i<evidence;++i) rows[0][i]="50";
        if (name=="wrong-schema") header[6]="Potential";
        if (name=="empty") rows.clear();
        auto path=output/("rating-"+name+".csv");
        {
            std::ofstream file(path);
            auto write=[&](auto const& fields) { bool comma=false; for (auto const& value:fields) {
                if (comma) file<<','; file<<value; comma=true; } file<<'\n'; };
            write(header); for (auto const& row:rows) write(row);
        }
        club->SetWriteableID(88); club->SetIsWriteable(false);
        bool rejected=false; RatingPlanResult result;
        try { result=ApplyRatingPlan(db,path,name=="preview"); }
        catch (std::exception const&) { rejected=true; }
        if (club->GetIsWriteable()) throw std::runtime_error("Rating rejection changed disabled club state");
        club->SetIsWriteable(true);
        if (club->GetWriteableID()!=88) throw std::runtime_error("Rating normalization lost hidden club ID");
        RatingHashScope hashes(db);
        if (name=="valid" || name=="preview") {
            if (rejected || result.players!=2 || result.attributes!=74 || first->mAttributes.Finishing!=65
                || first->mTalent!=7 || first->mPotential!=70 || first->mGeneralExperience!=9 || first->mPositionBias[17]!=100)
                throw std::runtime_error("Native rating plan failed or changed protected state");
        }
        else {
            if (name=="stale-hash") first->mTalent=7;
            if (!rejected || hashes.hash(*first)!=beforeFirst || hashes.hash(*second)!=beforeSecond)
                throw std::runtime_error("Rating rejection was not atomic: "+name);
        }
        ++cases;
    }
    {
        // Exercise the actual upstream serializer: every allowed field must
        // occupy and survive its own FM13 slot, including goalkeeper fields.
        FifamPlayerAttributes before,after;
        UChar value=1;
        for (auto const& field:RatingAttributes13()) before.*(field.value)=value++;
        std::wstring serialized;
        { FifamWriter writer(&serialized,13,FifamVersion(0x2013,0x12)); before.Write(writer); }
        { FifamReader reader(&serialized,13,FifamVersion(0x2013,0x12)); after.Read(reader); }
        if (RatingAttributes13().size()!=37) throw std::runtime_error("Unexpected FM13 attribute coverage");
        for (auto const& field:RatingAttributes13()) if (before.*(field.value)!=after.*(field.value))
            throw std::runtime_error("Rating field did not survive native serializer");
        ++cases;
    }
    {
        FifamDatabase db;
        auto country=db.CreateCountry(14); auto club=db.CreateClub(country);
        club->mUniqueID=917505; db.AddClubToMap(club);
        auto player=db.CreatePlayer(club,11); player->mFirstName=L"Canonical";
        player->mBirthday=FifamDate(2,1,2000); player->mAttributes.Pace=65;
        auto directory=output/"rating-protected"; std::filesystem::create_directories(directory);
        ExportPlayerSemantics(db,directory/"native_player_semantics.csv");
        ExportRatingInspection(db,directory/"before.csv");
        auto row=[&](std::string const& name) { std::ifstream f(directory/name); std::string line;
            std::getline(f,line); std::getline(f,line); return PlanCsv(line); };
        auto before=row("before.csv");
        if (before[11]!=row("native_player_semantics.csv")[19] || player->mAttributes.Pace!=65)
            throw std::runtime_error("Rating baseline hash differs from canonical serializer");
        player->mAttributes.Pace=66; ExportRatingInspection(db,directory/"attribute.csv");
        if (row("attribute.csv")[11]==before[11] || row("attribute.csv")[12]!=before[12])
            throw std::runtime_error("Protected hash masks more than the persisted attributes");
        player->mTalent=7; ExportRatingInspection(db,directory/"potential.csv");
        if (row("potential.csv")[12]==before[12]) throw std::runtime_error("Talent alteration escaped protected hash");
        ++cases;
    }
    std::ofstream report(output/"NATIVE_TESTS.json");
    report<<"{\"status\":\"PASS\",\"tests\":"<<(99+cases)
        <<",\"scope\":\"99 prior native cases plus20 rating cases: atomicity, full baseline identity, source and level guards,37 native attribute slots and protected serialization\"}\n";
}
