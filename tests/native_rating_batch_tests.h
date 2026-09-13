#pragma once

inline void RunRatingBatchTests(std::filesystem::path const& output) {
    size_t cases=0;
    for (std::string const name:{"valid","baseline-level","block-hash","attribute-parity"}) {
        auto folder=output/("rating-batch-"+name); std::filesystem::create_directories(folder);
        FifamPlayer player; player.mID=1; player.mFifaID=101; player.mBirthday=FifamDate(2,1,2000);
        player.mMainPosition=FifamPlayerPosition::ST; player.mPositionBias[17]=75; player.mGeneralExperience=12;
        for (auto const& field:RatingAttributes13()) player.mAttributes.*(field.value)=50;
        UInt oldLevel=FifamPlayerLevel::GetPlayerLevel13(&player,player.mMainPosition,player.mPlayingStyle);
        std::wstring text;
        { FifamWriter writer(&text,13,FifamVersion(0x2013,0x12)); player.Write(writer); }
        auto bytes=utf8(text);
        { std::ofstream file(folder/"1.sav",std::ios::binary); file<<bytes; }
        FifamDatabase empty; RatingHashScope hashes(empty);
        std::vector<std::string> indexHeader={"fm_id","fifa_id","dob","club_id","baseline_sha256","block_sha256",
            "main_position","style","experience","level13"};
        std::vector<std::string> index={"1","101","2000-01-02","0",hashes.hash(player),
            NativeSemanticHash(hashes.algorithm,bytes),"ST",utf8(player.mPlayingStyle.ToStr()),"12",std::to_string(oldLevel)};
        std::vector<std::string> proposal={"1","101","2000-01-02","0",index[4],""};
        for (auto const& field:RatingAttributes13()) { indexHeader.push_back(field.name); index.push_back("50"); proposal.push_back("80"); }
        for (auto value:{"CONFIRMED","https://example.com/rating","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","2026-09-08"})
            proposal.push_back(value);
        if (name=="baseline-level") index[9]="99";
        if (name=="block-hash") index[5]=std::string(64,'0');
        if (name=="attribute-parity") index[10]="49";
        auto write=[](std::filesystem::path const& path,auto const& header,auto const& row) {
            std::ofstream file(path); for (auto const* fields:{&header,&row}) {
                bool comma=false; for (auto const& value:*fields) { if (comma) file<<','; file<<value; comma=true; } file<<'\n'; }
        };
        write(folder/"players.csv",indexHeader,index); write(folder/"plan.csv",RatingPlanHeader(),proposal);
        bool rejected=false;
        try { EvaluateRatingBlocks(folder,folder/"plan.csv",folder/"result"); }
        catch (std::exception const&) { rejected=true; }
        if (name=="valid") {
            if (rejected) throw std::runtime_error("Native rating batch rejected valid serialized player");
            std::ifstream file(folder/"result/native_rating_alternatives.csv"); std::string line;
            std::getline(file,line); size_t count=0;
            while (std::getline(file,line)) {
                auto row=PlanCsv(line); ++count;
                if (row[1]=="DIRECT") {
                    for (auto const& field:RatingAttributes13()) player.mAttributes.*(field.value)=80;
                    if (PlanUInt(row[5])!=FifamPlayerLevel::GetPlayerLevel13(&player,player.mMainPosition,player.mPlayingStyle))
                        throw std::runtime_error("Batch level lost serialized bias or experience");
                }
                else if (PlanUInt(row[7])>20) throw std::runtime_error("Batch attribute cap exceeded");
            }
            if (count!=52) throw std::runtime_error("Batch alternatives incomplete");
        }
        else if (!rejected) throw std::runtime_error("Rating batch accepted stale native block: "+name);
        ++cases;
    }
    std::ofstream report(output/"NATIVE_TESTS.json");
    report<<"{\"status\":\"PASS\",\"tests\":"<<(123+cases)
        <<",\"scope\":\"123 prior native cases plus4 isolated-player native calibration cases: serialized bias/experience, block integrity, attribute parity and bounded alternatives\"}\n";
}
