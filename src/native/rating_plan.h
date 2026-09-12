#pragma once

struct RatingAttribute { char const* name; UChar FifamPlayerAttributes::* value; };
inline std::vector<RatingAttribute> const& RatingAttributes13() {
    static std::vector<RatingAttribute> const fields={
#define FM27_RATING_FIELD(name) {#name,&FifamPlayerAttributes::name}
        FM27_RATING_FIELD(BallControl),FM27_RATING_FIELD(Dribbling),FM27_RATING_FIELD(Finishing),
        FM27_RATING_FIELD(ShotPower),FM27_RATING_FIELD(LongShots),FM27_RATING_FIELD(Volleys),
        FM27_RATING_FIELD(Crossing),FM27_RATING_FIELD(Passing),FM27_RATING_FIELD(LongPassing),
        FM27_RATING_FIELD(Header),FM27_RATING_FIELD(TackleStanding),FM27_RATING_FIELD(TackleSliding),
        FM27_RATING_FIELD(ManMarking),FM27_RATING_FIELD(Acceleration),FM27_RATING_FIELD(Pace),
        FM27_RATING_FIELD(Agility),FM27_RATING_FIELD(Jumping),FM27_RATING_FIELD(Strength),
        FM27_RATING_FIELD(Stamina),FM27_RATING_FIELD(Balance),FM27_RATING_FIELD(PosOffensive),
        FM27_RATING_FIELD(PosDefensive),FM27_RATING_FIELD(Vision),FM27_RATING_FIELD(Aggression),
        FM27_RATING_FIELD(Reactions),FM27_RATING_FIELD(Composure),FM27_RATING_FIELD(Consistency),
        FM27_RATING_FIELD(TacticAwareness),FM27_RATING_FIELD(FreeKicks),FM27_RATING_FIELD(Corners),
        FM27_RATING_FIELD(PenaltyShot),FM27_RATING_FIELD(Diving),FM27_RATING_FIELD(Handling),
        FM27_RATING_FIELD(Positioning),FM27_RATING_FIELD(OneOnOne),FM27_RATING_FIELD(Reflexes),
        FM27_RATING_FIELD(Kicking)
#undef FM27_RATING_FIELD
    };
    return fields;
}

// Same UID-normalized native serialization as ExportPlayerSemantics. The scope
// restores even disabled club write IDs, including when a proposal is rejected.
struct RatingHashScope {
    struct Saved { FifamClub* club; bool writable; UInt id,uid; };
    std::vector<Saved> saved;
    BCRYPT_ALG_HANDLE algorithm=nullptr;
    explicit RatingHashScope(FifamDatabase& db) {
        saved.reserve(db.mClubs.size()+db.mCountries.size());
        if (BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)
            throw std::runtime_error("Cannot initialize rating SHA256");
        auto normalize=[&](FifamClub* club) {
            bool writable=club->GetIsWriteable(); club->SetIsWriteable(true);
            saved.push_back({club,writable,club->GetWriteableID(),club->GetWriteableUniqueID()});
            club->SetWriteableID(club->mUniqueID); club->SetWriteableUniqueID(club->mUniqueID);
        };
        for (auto club:db.mClubs) normalize(club);
        for (auto country:db.mCountries) if (country) normalize(&country->mNationalTeam);
    }
    RatingHashScope(RatingHashScope const&)=delete;
    RatingHashScope& operator=(RatingHashScope const&)=delete;
    ~RatingHashScope() {
        for (auto const& old:saved) {
            old.club->SetWriteableID(old.id); old.club->SetWriteableUniqueID(old.uid);
            old.club->SetIsWriteable(old.writable);
        }
        BCryptCloseAlgorithmProvider(algorithm,0);
    }
    std::string hash(FifamPlayer& player) const {
        std::wstring text;
        { FifamWriter writer(&text,13,FifamVersion(0x2013,0x12)); player.Write(writer); }
        return NativeSemanticHash(algorithm,utf8(text));
    }
};

struct RatingAttributeRestore {
    FifamPlayer& player;
    FifamPlayerAttributes original;
    explicit RatingAttributeRestore(FifamPlayer& p):player(p),original(p.mAttributes) {}
    ~RatingAttributeRestore() { player.mAttributes=original; }
};

inline std::vector<std::string> RatingPlanHeader() {
    std::vector<std::string> header={"fm_id","fifa_id","dob","club_id","baseline_sha256","expected_level13"};
    for (auto const& field:RatingAttributes13()) header.push_back(field.name);
    for (auto field:{"status","source","source_sha256","snapshot_date"}) header.push_back(field);
    return header;
}

struct RatingPlanResult { size_t players=0,attributes=0; std::string snapshot; };
inline RatingPlanResult ApplyRatingPlan(FifamDatabase& db,std::filesystem::path const& path,bool preview=false) {
    std::ifstream input(path,std::ios::binary);
    if (!input) throw std::runtime_error("Cannot open rating plan");
    std::string line; std::getline(input,line);
    if (line.rfind("\xEF\xBB\xBF",0)==0) line.erase(0,3);
    auto header=RatingPlanHeader();
    if (PlanCsv(line)!=header) throw std::runtime_error("Unexpected rating plan schema");
    std::map<UInt,FifamPlayer*> people;
    for (auto player:db.mPlayers) if (!people.emplace(player->mID,player).second)
        throw std::runtime_error("Ambiguous native rating player ID");
    std::map<FifamPlayer*,FifamPlayerAttributes> proposals;
    RatingHashScope hashes(db);
    RatingPlanResult result;
    while (std::getline(input,line)) {
        if (line.empty() || line=="\r") continue;
        auto row=PlanCsv(line);
        size_t evidence=6+RatingAttributes13().size();
        if (row.size()!=header.size() || row[evidence]!="CONFIRMED"
            || row[evidence+1].rfind("https://",0)!=0 || row[evidence+1].size()<9
            || !std::regex_match(row[evidence+2],std::regex("[0-9a-f]{64}")))
            throw std::runtime_error("Unconfirmed or unbound rating row");
        PlanDate(row[evidence+3]);
        if (result.snapshot.empty()) result.snapshot=row[evidence+3];
        if (result.snapshot!=row[evidence+3]) throw std::runtime_error("Mixed rating snapshots");
        auto found=people.find(PlanUInt(row[0]));
        if (found==people.end()) throw std::runtime_error("Rating target does not exist");
        auto player=found->second;
        if (player->mFifaID!=PlanUInt(row[1]) || player->mBirthday!=PlanDate(row[2])
            || (player->mClub?player->mClub->mUniqueID:0)!=PlanUInt(row[3])
            || hashes.hash(*player)!=row[4])
            throw std::runtime_error("Rating baseline identity or full serialization differs");
        auto attributes=player->mAttributes;
        size_t changed=0,index=6;
        for (auto const& field:RatingAttributes13()) {
            auto value=PlanUInt(row[index++]);
            if (value>99) throw std::runtime_error("Rating attribute outside FM13 range");
            if (attributes.*(field.value)!=value) ++changed;
            attributes.*(field.value)=static_cast<UChar>(value);
        }
        if (!changed) throw std::runtime_error("Rating plan contains unchanged player");
        if (!preview || !row[5].empty()) {
            auto expected=PlanUInt(row[5]);
            RatingAttributeRestore restore(*player); player->mAttributes=attributes;
            if (expected>99 || FifamPlayerLevel::GetPlayerLevel13(player,player->mMainPosition,player->mPlayingStyle)!=expected)
                throw std::runtime_error("Proposed native rating level differs from reviewed value");
        }
        if (!proposals.emplace(player,attributes).second) throw std::runtime_error("Duplicate rating target");
        result.attributes+=changed;
    }
    if (proposals.empty()) throw std::runtime_error("Empty rating plan");
    // All validation, including native level previews, finishes before mutation.
    for (auto const& proposal:proposals) proposal.first->mAttributes=proposal.second;
    result.players=proposals.size();
    return result;
}

inline void ExportRatingInspection(FifamDatabase& db,std::filesystem::path const& path) {
    RatingHashScope hashes(db);
    std::ofstream file(path,std::ios::binary);
    if (!file) throw std::runtime_error("Cannot create rating inspection");
    file<<"fm_id,fifa_id,dob,club_id,name,main_position,style,experience,level13,best_style,level13_best_style,serialized_sha256,protected_sha256";
    for (auto const& field:RatingAttributes13()) file<<','<<field.name;
    file<<",talent,in_reserve,in_youth\n";
    std::vector<FifamPlayer*> ordered(db.mPlayers.begin(),db.mPlayers.end());
    std::sort(ordered.begin(),ordered.end(),[](auto a,auto b){return a->mID<b->mID;});
    for (auto player:ordered) {
        auto best=FifamPlayerLevel::GetBestStyleForPlayer(player);
        auto full=hashes.hash(*player);
        std::string protectedHash;
        { RatingAttributeRestore restore(*player);
          for (auto const& field:RatingAttributes13()) player->mAttributes.*(field.value)=0;
          protectedHash=hashes.hash(*player); }
        file<<player->mID<<','<<player->mFifaID<<','<<player->mBirthday.ToStringA()<<','
            <<(player->mClub?player->mClub->mUniqueID:0)<<','<<csv(player->GetName())<<','
            <<csv(player->mMainPosition.ToStr())<<','<<csv(player->mPlayingStyle.ToStr())<<','
            <<static_cast<UInt>(player->mGeneralExperience)<<','
            <<static_cast<UInt>(FifamPlayerLevel::GetPlayerLevel13(player,player->mMainPosition,player->mPlayingStyle))<<','
            <<csv(best.ToStr())<<','<<static_cast<UInt>(FifamPlayerLevel::GetPlayerLevel13(player,player->mMainPosition,best))
            <<','<<full<<','<<protectedHash;
        for (auto const& field:RatingAttributes13()) file<<','<<static_cast<UInt>(player->mAttributes.*(field.value));
        file<<','<<static_cast<UInt>(player->mTalent)<<','<<player->mInReserveTeam<<','<<player->mInYouthTeam<<'\n';
    }
    file.flush();
    if (!file) throw std::runtime_error("Native rating inspection write failed");
}
