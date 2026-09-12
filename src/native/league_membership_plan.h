#pragma once
#include "FifamCompLeague.h"

struct LeagueMembershipResult { size_t leagues=0,changedSlots=0; std::string snapshot; };

inline void RequireValidLeagueSchedule(FifamCompLeague const& league) {
    UInt n=league.mNumTeams,rounds=league.mNumRounds;
    if (n<2 || n>24 || rounds<1 || rounds>4) throw std::runtime_error("Unsupported native league fixture dimensions");
    UInt days=(n-1+n%2)*rounds;
    auto calendar=[&](Vector<UShort> const& dates,bool optional) {
        if (optional && dates.empty()) return;
        if (dates.size()!=days) throw std::runtime_error("Native league calendar count differs from format");
        UShort prior=0;
        for (auto day:dates) {
            if (day<1 || day>365 || day<=prior) throw std::runtime_error("Native league calendar is not strictly ordered");
            prior=day;
        }
    };
    calendar(league.mFirstSeasonMatchdays,false); calendar(league.mSecondSeasonMatchdays,true);
    if (league.mFixtures.size()!=days) throw std::runtime_error("Native fixture matchday count differs");
    std::map<std::pair<UInt,UInt>,UInt> pairs,directed;
    for (auto const& day:league.mFixtures) {
        if (day.size()!=n/2) throw std::runtime_error("Incorrect number of native matches in day");
        std::set<UInt> used;
        for (auto const& game:day) {
            UInt home=game.first,away=game.second;
            if (home<1 || home>n || away<1 || away>n || !used.insert(home).second || !used.insert(away).second)
                throw std::runtime_error("Native fixture repeats or misidentifies a team");
            ++pairs[{(std::min)(home,away),(std::max)(home,away)}]; ++directed[{home,away}];
        }
    }
    if (pairs.size()!=n*(n-1)/2) throw std::runtime_error("Native fixture opponent coverage is incomplete");
    for (auto const& pair:pairs) if (pair.second!=rounds) throw std::runtime_error("Native fixture pairing count differs");
    if (rounds%2==0) for (UInt home=1;home<=n;++home) for (UInt away=1;away<=n;++away)
        if (home!=away && directed[{home,away}]!=rounds/2) throw std::runtime_error("Native fixture home/away balance differs");
}

// Membership-only phase. Format/calendar/instruction changes need their own
// explicit plan; unspecified slots retain their exact native baseline membership.
inline LeagueMembershipResult ApplyLeagueMembershipPlan(FifamDatabase& db,std::filesystem::path const& path) {
    std::ifstream input(path,std::ios::binary);
    if (!input) throw std::runtime_error("Cannot read league membership plan");
    std::string line;
    std::getline(input,line);
    if (line.rfind("\xEF\xBB\xBF",0)==0) line.erase(0,3);
    if (PlanCsv(line)!=std::vector<std::string>{"competition_id","slot","old_club_id","old_team_type",
        "new_club_id","new_team_type","status","source","source_sha256","snapshot_date"})
        throw std::runtime_error("Unexpected league membership plan schema");
    struct Proposal { FifamCompLeague* league=nullptr; std::map<UInt,FifamClubLink> slots; };
    std::map<UInt,Proposal> proposals;
    std::map<UInt,FifamClub*> clubs;
    for (auto club:db.mClubs) if (!clubs.emplace(club->mUniqueID,club).second)
        throw std::runtime_error("Ambiguous native club ID");
    auto teamType=[](std::string const& value) {
        if (value=="FIRST") return FifamClubTeamType(FifamClubTeamType::First);
        if (value=="RESERVE") return FifamClubTeamType(FifamClubTeamType::Reserve);
        throw std::runtime_error("League team type must be FIRST or RESERVE");
    };
    LeagueMembershipResult result;
    while (std::getline(input,line)) {
        if (line.empty() || line=="\r") continue;
        auto row=PlanCsv(line);
        if (row.size()!=10 || row[6]!="CONFIRMED" || row[7].rfind("https://",0)!=0 || row[7].size()<9
            || !std::regex_match(row[8],std::regex("[0-9a-f]{64}")))
            throw std::runtime_error("Unconfirmed or unbound league membership row");
        PlanDate(row[9]);
        if (result.snapshot.empty()) result.snapshot=row[9];
        if (result.snapshot!=row[9]) throw std::runtime_error("Mixed league membership snapshots");
        UInt id=PlanUInt(row[0]),slot=PlanUInt(row[1]),oldId=PlanUInt(row[2]),newId=PlanUInt(row[4]);
        auto comp=db.GetCompetition(FifamCompID(id));
        if (!comp || !comp->AsLeague() || comp->mID.mType!=FifamCompType::League
            || comp->mID.mRegion.ToInt()<1 || comp->mID.mRegion.ToInt()>FifamDatabase::NUM_COUNTRIES)
            throw std::runtime_error("Membership plan target must be an existing domestic normal league");
        auto league=comp->AsLeague();
        if (!proposals.count(id)) RequireValidLeagueSchedule(*league);
        if (league->mNumTeams<2 || league->mNumTeams>24 || league->mTeams.size()!=league->mNumTeams
            || slot<1 || slot>league->mNumTeams)
            throw std::runtime_error("League format needs explicit separate review");
        auto const& old=league->mTeams[slot-1];
        auto oldType=teamType(row[3]),newType=teamType(row[5]);
        if (!old.mPtr || old.mPtr->mUniqueID!=oldId || old.mTeamType!=oldType || !clubs.count(newId))
            throw std::runtime_error("League membership baseline identity differs");
        auto target=clubs.at(newId);
        if (!target->mCountry || target->mCountry->mId!=league->mID.mRegion.ToInt())
            throw std::runtime_error("Club belongs to a different native country");
        auto& proposal=proposals[id]; proposal.league=league;
        if (!proposal.slots.emplace(slot,FifamClubLink(target,newType)).second)
            throw std::runtime_error("Duplicate league membership slot");
    }
    if (proposals.empty()) throw std::runtime_error("Empty league membership plan");
    using TeamKey=std::pair<UInt,UChar>;
    std::map<TeamKey,size_t> before,after;
    std::set<TeamKey> touched;
    for (auto const& entry:db.mCompMap) {
        auto league=entry.second->AsLeague();
        if (!league || league->mID.mType!=FifamCompType::League || league->mID.mRegion.ToInt()<1
            || league->mID.mRegion.ToInt()>FifamDatabase::NUM_COUNTRIES) continue;
        auto proposed=proposals.find(league->mID.ToInt());
        for (UInt i=0;i<league->mTeams.size();++i) {
            auto const& old=league->mTeams[i];
            bool supplied=proposed!=proposals.end() && proposed->second.slots.count(i+1);
            auto const& next=supplied?proposed->second.slots.at(i+1):old;
            if (old.mPtr) ++before[{old.mPtr->mUniqueID,old.mTeamType.ToInt()}];
            if (next.mPtr) ++after[{next.mPtr->mUniqueID,next.mTeamType.ToInt()}];
            if (supplied) {
                touched.insert({old.mPtr->mUniqueID,old.mTeamType.ToInt()});
                touched.insert({next.mPtr->mUniqueID,next.mTeamType.ToInt()});
                if (!(old==next)) ++result.changedSlots;
            }
        }
    }
    if (before!=after) throw std::runtime_error("League plan loses or duplicates a domestic team");
    for (auto const& team:touched) if (before[team]!=1 || after[team]!=1)
        throw std::runtime_error("A touched team has ambiguous native league membership");
    if (!result.changedSlots) throw std::runtime_error("League membership plan changes no slots");
    // All identities, destinations and global conservation checks precede mutation.
    for (auto const& entry:proposals) {
        auto const& proposal=entry.second;
        for (auto const& slot:proposal.slots) proposal.league->mTeams[slot.first-1]=slot.second;
    }
    result.leagues=proposals.size();
    return result;
}
