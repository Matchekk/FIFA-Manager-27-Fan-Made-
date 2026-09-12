#pragma once
#include "rating_plan.h"

inline std::wstring CreatePlanWide(std::string const& text) {
    if (text.empty()) return {};
    auto size=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,text.data(),static_cast<int>(text.size()),nullptr,0);
    if (size<=0) throw std::runtime_error("Invalid UTF-8 in player creation plan");
    std::wstring value(static_cast<size_t>(size),L'\0');
    MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,text.data(),static_cast<int>(text.size()),value.data(),size);
    return value;
}

struct CreatePlayerResult { size_t players=0; std::string snapshot; };
inline CreatePlayerResult ApplyCreatePlayerPlan(FifamDatabase& db,std::filesystem::path const& path) {
    std::ifstream input(path,std::ios::binary);
    if (!input) throw std::runtime_error("Cannot open player creation plan");
    std::string line; std::getline(input,line);
    if (line.rfind("\xEF\xBB\xBF",0)==0) line.erase(0,3);
    std::vector<std::string> header={"fm_id","player_tm_id","fifa_id","first_name","last_name","pseudonym",
        "dob","nationality1","nationality2","club_id","joined","contract_until","shirt_number","team_type",
        "position","rating_seed","status","source","source_sha256","snapshot_date"};
    if (PlanCsv(line)!=header) throw std::runtime_error("Unexpected player creation schema");
    struct Proposal { UInt id,tm,fifa,club,shirt,nation1,nation2,seed; std::wstring first,last,pseudonym;
        FifamDate dob,joined,until; bool reserve; FifamPlayerPosition position; };
    std::vector<Proposal> proposals;
    std::set<UInt> ids,tmIds;
    for (auto person:db.mPersonsMap) { ids.insert(person.first); if (person.second->mTmDeID) tmIds.insert(person.second->mTmDeID); }
    CreatePlayerResult result;
    while (std::getline(input,line)) {
        if (line.empty() || line=="\r") continue;
        auto row=PlanCsv(line);
        if (row.size()!=header.size() || row[16]!="CONFIRMED" || row[17].rfind("https://",0)!=0 ||
            !std::regex_match(row[18],std::regex("[0-9a-f]{64}")))
            throw std::runtime_error("Unconfirmed or unbound player creation row");
        Proposal p{}; p.id=PlanUInt(row[0]); p.tm=PlanUInt(row[1]); p.fifa=PlanUInt(row[2]);
        p.first=CreatePlanWide(row[3]); p.last=CreatePlanWide(row[4]); p.pseudonym=CreatePlanWide(row[5]);
        p.dob=PlanDate(row[6]); p.nation1=PlanUInt(row[7]); p.nation2=PlanUInt(row[8]); p.club=PlanUInt(row[9]);
        p.joined=PlanDate(row[10]); p.until=PlanDate(row[11]); p.shirt=PlanUInt(row[12]);
        p.reserve=row[13]=="RESERVE"; p.seed=PlanUInt(row[15]);
        if ((row[13]!="FIRST" && !p.reserve) || !p.position.SetFromStr(CreatePlanWide(row[14])) ||
            p.fifa!=0 || !p.id || !p.tm || ids.count(p.id) || tmIds.count(p.tm) ||
            !ids.insert(p.id).second || !tmIds.insert(p.tm).second || !db.GetClubFromUID(p.club,false) ||
            p.joined<p.dob || p.joined>PlanDate(row[19]) || p.until<PlanDate(row[19]) ||
            p.shirt>99 || p.nation1==0 || p.nation1>207 || p.nation2>207 || p.seed<35 || p.seed>60 ||
            p.first.size()>15 || p.last.empty() || p.last.size()>19 || p.pseudonym.size()>29)
            throw std::runtime_error("Player creation identity, club, chronology, or bounded defaults invalid");
        if (result.snapshot.empty()) result.snapshot=row[19];
        if (result.snapshot!=row[19] || result.snapshot!="2026-09-12") throw std::runtime_error("Mixed/stale creation snapshot");
        proposals.push_back(p);
    }
    if (proposals.empty()) throw std::runtime_error("Empty player creation plan");
    for (auto const& c:proposals) {
        auto club=db.GetClubFromUID(c.club,false);
        auto player=db.CreatePlayer(club,c.id);
        if (player->mID!=c.id) throw std::runtime_error("Creation ID allocation changed after validation");
        player->mTmDeID=c.tm; player->mFifaID=0; player->mFirstName=c.first; player->mLastName=c.last;
        player->mPseudonym=c.pseudonym; player->mBirthday=c.dob; player->mNationality[0].SetFromInt(static_cast<UChar>(c.nation1));
        player->mNationality[1].SetFromInt(static_cast<UChar>(c.nation2)); player->mMainPosition=c.position;
        player->mPositionBias=FifamPlayerLevel::GetDefaultBiasValues(c.position); player->mPlayingStyle.SetFromInt(0);
        player->mRightFoot=4; player->mLeftFoot=1; player->mTalent=3; player->mTacticalEducation=3;
        player->mGeneralExperience=0; player->mIsRealPlayer=true; player->mHeight=178; player->mWeight=70;
        for (auto const& field:RatingAttributes13()) player->mAttributes.*(field.value)=static_cast<UChar>(c.seed);
        player->mContract.mJoined=c.joined; player->mContract.mValidUntil=c.until;
        player->mInReserveTeam=c.reserve; player->mInYouthTeam=false;
        if (c.reserve) player->mShirtNumberReserveTeam=static_cast<UChar>(c.shirt);
        else player->mShirtNumberFirstTeam=static_cast<UChar>(c.shirt);
    }
    result.players=proposals.size(); return result;
}
