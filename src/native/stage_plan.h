#pragma once
#include "FifamDatabase.h"
#include "FifamPlayer.h"
#include <chrono>
#include <fstream>
#include <map>
#include <regex>
#include <set>
#include <stdexcept>

inline std::vector<std::string> PlanCsv(std::string line) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    std::vector<std::string> result;
    std::string field;
    bool quoted = false;
    for (size_t i = 0; i < line.size(); ++i) {
        if (line[i] == '"') {
            if (quoted && i + 1 < line.size() && line[i + 1] == '"') { field += '"'; ++i; }
            else quoted = !quoted;
        }
        else if (line[i] == ',' && !quoted) { result.push_back(field); field.clear(); }
        else field += line[i];
    }
    if (quoted) throw std::runtime_error("Unclosed CSV quote");
    result.push_back(field);
    return result;
}

inline UInt PlanUInt(std::string const& value) {
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::runtime_error("Expected unsigned plan integer");
    auto parsed = std::stoull(value);
    if (parsed > 0xFFFFFFFFull) throw std::runtime_error("Plan integer overflow");
    return static_cast<UInt>(parsed);
}

inline FifamDate PlanDate(std::string const& value) {
    if (!std::regex_match(value, std::regex("[0-9]{4}-[0-9]{2}-[0-9]{2}")))
        throw std::runtime_error("Invalid plan date format");
    auto y = PlanUInt(value.substr(0,4)), m = PlanUInt(value.substr(5,2)), d = PlanUInt(value.substr(8,2));
    if (y < 1900 || y > 2100 || !std::chrono::year_month_day(std::chrono::year(static_cast<int>(y)),
        std::chrono::month(m), std::chrono::day(d)).ok()) throw std::runtime_error("Invalid calendar date");
    return FifamDate(d,m,y);
}

inline size_t ApplyStagePlan(FifamDatabase& db, std::filesystem::path const& path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) throw std::runtime_error("Cannot open staging plan");
    std::string line;
    std::getline(stream,line);
    if (line.rfind("\xEF\xBB\xBF",0)==0) line.erase(0,3);
    auto header=PlanCsv(line);
    std::vector<std::string> expected={"fm_id","fifa_id","dob","old_club_id","new_club_id","joined",
        "contract_until","shirt_number","team_type","status","source","source_sha256","snapshot_date"};
    if (header!=expected) throw std::runtime_error("Unexpected staging plan schema");
    struct Change { FifamPlayer* player; FifamClub* target; FifamDate joined; FifamDate until; UInt number; bool reserve; };
    std::vector<Change> changes;
    std::map<UInt,FifamPlayer*> byId;
    for (auto p:db.mPlayers) if (!byId.emplace(p->mID,p).second) throw std::runtime_error("Duplicate native player ID");
    std::set<UInt> seen;
    while (std::getline(stream,line)) {
        if (line.empty()) continue;
        auto f=PlanCsv(line);
        if (f.size()!=expected.size() || f[9]!="CONFIRMED" || f[10].rfind("https://",0)!=0 ||
            !std::regex_match(f[11],std::regex("[0-9a-f]{64}"))) throw std::runtime_error("Unconfirmed or malformed plan row");
        auto id=PlanUInt(f[0]);
        if (!seen.insert(id).second || !byId.count(id)) throw std::runtime_error("Missing/repeated planned person");
        auto p=byId.at(id);
        auto old=p->mClub?p->mClub->mUniqueID:0;
        if (p->mFifaID!=PlanUInt(f[1]) || p->mBirthday!=PlanDate(f[2]) || old!=PlanUInt(f[3]))
            throw std::runtime_error("Native baseline identity/club precondition failed");
        auto target=db.GetClubFromUID(PlanUInt(f[4]),false);
        if (!target || target->mIsNationalTeam) throw std::runtime_error("Invalid destination club");
        auto joined=PlanDate(f[5]), until=PlanDate(f[6]), snapshot=PlanDate(f[12]);
        if (joined>snapshot || until<snapshot || joined<p->mBirthday || snapshot<FifamDate(8,9,2026))
            throw std::runtime_error("Invalid effective contract/snapshot dates");
        auto number=PlanUInt(f[7]);
        if (number>99 || (f[8]!="FIRST" && f[8]!="RESERVE")) throw std::runtime_error("Invalid team/number");
        auto& c=p->mStartingConditions;
        if (c.mRetirement.mEnabled || c.mLoan.mEnabled || c.mFutureTransfer.mEnabled || c.mFutureLoan.mEnabled ||
            c.mFutureJoin.mEnabled || c.mFutureReLoan.mEnabled || c.mFutureLeave.mEnabled || c.mBanUntil.mEnabled || p->mContract.mLoaned)
            throw std::runtime_error("Complex existing condition requires a typed loan/timeline plan");
        changes.push_back({p,target,joined,until,number,f[8]=="RESERVE"});
    }
    if (changes.empty()) throw std::runtime_error("Empty staging plan");
    // All rows were checked before any mutation. Only the in-memory copy changes.
    for (auto const& c:changes) {
        auto p=c.player;
        if (p->mClub!=c.target) {
            if (p->mClub) {
                auto& members=p->mClub->mPlayers;
                members.erase(std::remove(members.begin(),members.end(),p),members.end());
                for (auto& captain:p->mClub->mCaptains) if (captain==p) captain=nullptr;
            }
            c.target->mPlayers.push_back(p);
            p->mClub=c.target;
            p->mIsCaptain=false;
        }
        p->mContract.mJoined=c.joined;
        p->mContract.mValidUntil=c.until;
        p->mInReserveTeam=c.reserve;
        p->mInYouthTeam=false;
        if (c.reserve) p->mShirtNumberReserveTeam=static_cast<UChar>(c.number);
        else p->mShirtNumberFirstTeam=static_cast<UChar>(c.number);
    }
    for (auto club:db.mClubs) {
        std::set<FifamPlayer*> members;
        for (auto p:club->mPlayers)
            if (p->mClub!=club || !members.insert(p).second) throw std::runtime_error("Inconsistent club membership after staging");
    }
    return changes.size();
}
