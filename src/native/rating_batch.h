#pragma once

// Read isolated, source-hashed PLAYER blocks with the actual FM13 reader. No
// database or game is written; each alternative is evaluated by GetPlayerLevel13.
inline void EvaluateRatingBlocks(std::filesystem::path const& blocks,std::filesystem::path const& plan,
    std::filesystem::path const& output) {
    if (std::filesystem::exists(output)) throw std::runtime_error("Rating batch output already exists");
    auto read=[](std::filesystem::path const& path) {
        std::ifstream file(path,std::ios::binary);
        if (!file) throw std::runtime_error("Cannot open rating batch input");
        std::vector<std::vector<std::string>> rows;
        std::string line;
        while (std::getline(file,line)) {
            if (rows.empty() && line.rfind("\xEF\xBB\xBF",0)==0) line.erase(0,3);
            if (!line.empty() && line!="\r") rows.push_back(PlanCsv(line));
        }
        return rows;
    };
    auto index=read(blocks/"players.csv"),planned=read(plan);
    std::vector<std::string> expected={"fm_id","fifa_id","dob","club_id","baseline_sha256","block_sha256",
        "main_position","style","experience","level13"};
    for (auto const& field:RatingAttributes13()) expected.push_back(field.name);
    if (index.empty() || index[0]!=expected || planned.empty() || planned[0]!=RatingPlanHeader())
        throw std::runtime_error("Unexpected rating batch schema");
    std::map<UInt,std::vector<std::string>> proposals;
    for (size_t n=1;n<planned.size();++n) {
        auto const& row=planned[n];
        if (row.size()!=RatingPlanHeader().size() || !proposals.emplace(PlanUInt(row[0]),row).second)
            throw std::runtime_error("Invalid or duplicate rating batch proposal");
    }
    if (proposals.empty() || index.size()!=proposals.size()+1) throw std::runtime_error("Rating batch coverage differs");
    FifamDatabase empty;
    RatingHashScope hashes(empty);
    std::set<UInt> seen;
    std::filesystem::create_directories(output);
    std::ofstream file(output/"native_rating_alternatives.csv",std::ios::binary);
    if (!file) throw std::runtime_error("Cannot create rating alternatives");
    file<<"fm_id,variant,source_percent,offset,attribute_cap,level13,changed_attributes,max_attribute_delta,source_squared_distance\n";
    size_t alternatives=0;
    for (size_t n=1;n<index.size();++n) {
        auto const& baseline=index[n];
        if (baseline.size()!=expected.size()) throw std::runtime_error("Invalid rating block index row");
        UInt id=PlanUInt(baseline[0]);
        if (!seen.insert(id).second || !proposals.count(id)) throw std::runtime_error("Rating block identity coverage differs");
        auto const& proposal=proposals.at(id);
        for (size_t k=0;k<5;++k) if (proposal[k]!=baseline[k])
            throw std::runtime_error("Rating plan differs from block baseline");
        auto path=blocks/(std::to_string(id)+".sav");
        std::ifstream raw(path,std::ios::binary);
        std::string bytes((std::istreambuf_iterator<char>(raw)),std::istreambuf_iterator<char>());
        if (!raw || NativeSemanticHash(hashes.algorithm,bytes)!=baseline[5])
            throw std::runtime_error("Rating player block hash differs");
        FifamPlayer player;
        { FifamReader reader(path,13,FifamVersion(0x2013,0x12)); player.Read(reader); }
        if (player.mFifaID!=PlanUInt(baseline[1]) || player.mBirthday!=PlanDate(baseline[2])
            || utf8(player.mMainPosition.ToStr())!=baseline[6] || utf8(player.mPlayingStyle.ToStr())!=baseline[7]
            || player.mGeneralExperience!=PlanUInt(baseline[8])
            || FifamPlayerLevel::GetPlayerLevel13(&player,player.mMainPosition,player.mPlayingStyle)!=PlanUInt(baseline[9]))
            throw std::runtime_error("Isolated native reader disagrees with validated baseline level inputs");
        auto original=player.mAttributes;
        size_t fieldIndex=0;
        for (auto const& field:RatingAttributes13()) {
            if (original.*(field.value)!=PlanUInt(baseline[10+fieldIndex]) || PlanUInt(proposal[6+fieldIndex])>99)
                throw std::runtime_error("Rating block attribute differs");
            ++fieldIndex;
        }
        auto evaluate=[&](char const* variant,Int percent,Int offset,Int cap) {
            size_t column=6; UInt changed=0,maxDelta=0,distance=0;
            for (auto const& field:RatingAttributes13()) {
                Int old=original.*(field.value),source=static_cast<Int>(PlanUInt(proposal[column++]));
                Int value=old;
                if (source!=old) {
                    value=(old*(100-percent)+source*percent+50)/100+offset;
                    value=(std::max)(0,(std::max)(old-cap,(std::min)(99,(std::min)(old+cap,value))));
                }
                player.mAttributes.*(field.value)=static_cast<UChar>(value);
                UInt delta=static_cast<UInt>(std::abs(value-old));
                if (delta) ++changed;
                maxDelta=(std::max)(maxDelta,delta);
                distance+=static_cast<UInt>((value-source)*(value-source));
            }
            auto level=FifamPlayerLevel::GetPlayerLevel13(&player,player.mMainPosition,player.mPlayingStyle);
            file<<id<<','<<variant<<','<<percent<<','<<offset<<','<<cap<<','<<static_cast<UInt>(level)<<','
                <<changed<<','<<maxDelta<<','<<distance<<'\n';
            ++alternatives;
        };
        evaluate("DIRECT",100,0,99);
        for (Int percent:{50,75,100}) for (Int offset=-8;offset<=8;++offset) evaluate("CALIBRATION_GRID",percent,offset,20);
    }
    file.flush();
    if (!file) throw std::runtime_error("Rating batch output failed");
    std::ofstream report(output/"NATIVE_RATING_BATCH.json");
    report<<"{\"status\":\"NATIVE_LEVEL_ALTERNATIVES_EVALUATED_NOT_CALIBRATED\",\"players\":"<<seen.size()
        <<",\"alternatives\":"<<alternatives<<",\"release_ready\":false}\n";
    std::cout<<"NATIVE_RATING_ALTERNATIVES players="<<seen.size()<<" alternatives="<<alternatives<<'\n';
}
