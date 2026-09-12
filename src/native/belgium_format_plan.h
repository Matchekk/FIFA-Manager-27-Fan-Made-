#pragma once
#include "league_membership_plan.h"
#include "FifamCompPool.h"
#include "FifamCompRound.h"

// Native competition authoring, never an engine patch. The caller binds the
// input database and this complete membership CSV in its immutable manifest.
inline Vector<Vector<Pair<UChar,UChar>>> BelgiumRoundRobin(UInt count) {
    UInt even=count+count%2;
    Vector<UInt> ring;
    for (UInt n=1;n<=even;++n) ring.push_back(n);
    Vector<Vector<Pair<UChar,UChar>>> first;
    for (UInt round=0;round<even-1;++round) {
        Vector<Pair<UChar,UChar>> day;
        for (UInt i=0;i<even/2;++i) {
            auto a=ring[i],b=ring[even-1-i];
            if (a>count || b>count) continue;
            if ((round+i)%2) std::swap(a,b);
            day.push_back({static_cast<UChar>(a),static_cast<UChar>(b)});
        }
        first.push_back(day);
        auto last=ring.back();
        for (UInt i=even-1;i>1;--i) ring[i]=ring[i-1];
        ring[1]=last;
    }
    auto fixtures=first;
    for (auto day:first) {
        for (auto& match:day) std::swap(match.first,match.second);
        fixtures.push_back(day);
    }
    return fixtures;
}

struct BelgiumFormatResult { size_t leagues=0; size_t competitions=0; };

inline BelgiumFormatResult ApplyBelgium2026Format(FifamDatabase& db,std::filesystem::path const& path) {
    auto comp=[&](UInt id) {
        auto p=db.GetCompetition(FifamCompID(id));
        if (!p) throw std::runtime_error("Belgium format missing baseline competition");
        return p;
    };
    auto top=comp(117506048)->AsLeague(),second=comp(117506049)->AsLeague();
    auto topPool=comp(119013376)->AsPool(),secondPool=comp(119013377)->AsPool();
    auto thirdPool=comp(119013378)->AsPool();
    auto semi=comp(117964800)->AsRound(),final=comp(117964801)->AsRound();
    auto obsolete=comp(117964802)->AsRound();
    if (!top || !second || !topPool || !secondPool || !thirdPool || !semi || !final || !obsolete ||
        top->mNumTeams!=16 || second->mNumTeams!=17 || topPool->mNumTeams!=16 || secondPool->mNumTeams!=17 ||
        top->mNumRounds!=2 || second->mNumRounds!=2 || semi->mNumTeams!=4 || final->mNumTeams!=2)
        throw std::runtime_error("Belgium format baseline differs from reviewed16/17 topology");
    RequireValidLeagueSchedule(*top); RequireValidLeagueSchedule(*second);
    auto topDates=second->mFirstSeasonMatchdays,topDates2=second->mSecondSeasonMatchdays;
    auto secondDates=top->mFirstSeasonMatchdays,secondDates2=top->mSecondSeasonMatchdays;
    // Reuse supported domestic34/30-date calendars. This is a modeled game
    // calendar, not a claim to reproduce official TV fixture dates.
    if (topDates.size()!=34 || secondDates.size()!=30 ||
        (!topDates2.empty() && topDates2.size()!=34) || (!secondDates2.empty() && secondDates2.size()!=30))
        throw std::runtime_error("Belgium calendar donor dimensions differ");
    std::ifstream input(path,std::ios::binary); std::string line;
    if (!input || !std::getline(input,line)) throw std::runtime_error("Missing Belgium membership input");
    if (line.rfind("\xEF\xBB\xBF",0)==0) line.erase(0,3);
    if (PlanCsv(line)!=std::vector<std::string>{"competition_id","club_id","team_type"})
        throw std::runtime_error("Unexpected Belgium membership schema");
    std::map<UInt,Vector<FifamClubLink>> teams;
    using TeamKey=std::pair<UInt,UChar>;
    std::set<TeamKey> proposed,boundary;
    while (std::getline(input,line)) {
        if (line.empty() || line=="\r") continue;
        auto row=PlanCsv(line);
        if (row.size()!=3) throw std::runtime_error("Malformed Belgium membership row");
        auto id=PlanUInt(row[0]),clubID=PlanUInt(row[1]);
        auto club=db.GetClubFromUID(clubID,false);
        if (!club || !club->mCountry || club->mCountry->mId!=7 || (row[2]!="FIRST" && row[2]!="RESERVE"))
            throw std::runtime_error("Invalid Belgium league/club/team identity");
        auto type=row[2]=="FIRST" ? FifamClubTeamType(FifamClubTeamType::First)
                                   : FifamClubTeamType(FifamClubTeamType::Reserve);
        // Explicit permission for a source-proven transition across the bottom
        // of the modeled pyramid. ID0 is a plan marker, never a competition ID
        // written to the database. The frozen source manifest must bind proof.
        if (id==0) {
            if (!boundary.emplace(clubID,type.ToInt()).second)
                throw std::runtime_error("Duplicate Belgium boundary declaration");
            continue;
        }
        auto league=comp(id)->AsLeague();
        if (!league || league->mID.mRegion.ToInt()!=7 || league->mID.mType!=FifamCompType::League)
            throw std::runtime_error("Invalid Belgium league identity");
        if (id==117506048 && type!=FifamClubTeamType::First) throw std::runtime_error("Reserve cannot enter Belgian top flight");
        if (!proposed.emplace(clubID,type.ToInt()).second) throw std::runtime_error("Repeated Belgium team");
        teams[id].push_back(FifamClubLink(club,type));
    }
    if (teams[117506048].size()!=18 || teams[117506049].size()!=15)
        throw std::runtime_error("Belgium requires complete18/15 membership");
    std::map<TeamKey,size_t> before,after;
    std::map<TeamKey,UInt> beforeLeague,afterLeague;
    for (auto const& item:db.mCompMap) {
        auto league=item.second->AsLeague();
        if (!league || league->mID.mType!=FifamCompType::League || league->mID.mRegion.ToInt()!=7) continue;
        auto id=league->mID.ToInt();
        for (auto const& link:league->mTeams) if (link.mPtr) {
            TeamKey key{link.mPtr->mUniqueID,link.mTeamType.ToInt()};++before[key];beforeLeague[key]=id;
        }
        auto it=teams.find(id);
        if (it!=teams.end() && id!=117506048 && id!=117506049 && it->second.size()!=league->mNumTeams)
            throw std::runtime_error("Belgium dependency league must preserve size");
        for (auto const& link:it==teams.end()?league->mTeams:it->second)
            if (link.mPtr) {
                TeamKey key{link.mPtr->mUniqueID,link.mTeamType.ToInt()};++after[key];afterLeague[key]=id;
            }
    }
    auto lowest=[](UInt id) { return id>=117506052 && id<=117506054; };
    for (auto const& key:boundary) {
        size_t oldCount=before.count(key)?before.at(key):0,newCount=after.count(key)?after.at(key):0;
        bool enters=oldCount==0 && newCount==1 && lowest(afterLeague.at(key));
        bool leaves=oldCount==1 && newCount==0 && lowest(beforeLeague.at(key));
        if (!enters && !leaves) throw std::runtime_error("Belgium boundary must cross the lowest modeled tier exactly once");
    }
    auto conservedBefore=before,conservedAfter=after;
    for (auto const& key:boundary) { conservedBefore.erase(key);conservedAfter.erase(key); }
    if (conservedBefore!=conservedAfter) throw std::runtime_error("Belgium membership loses an undeclared team");
    for (auto const& item:after) if (item.second!=1) throw std::runtime_error("Duplicate Belgium league membership");
    // The only third-pool amendment is its direct second-tier relegation input.
    FifamInstruction::GET_TAB_X_TO_Y* relegationInput=nullptr;
    thirdPool->mInstructions.ForAll([&](FifamAbstractInstruction* instruction) {
        auto p=dynamic_cast<FifamInstruction::GET_TAB_X_TO_Y*>(instruction);
        if (p && p->mLeague==second->mID) {
            if (relegationInput || p->mLeagueStartPosition!=16 || p->mNumTeams!=2)
                throw std::runtime_error("Belgium third-tier relegation input differs");
            relegationInput=p;
        }
    });
    if (!relegationInput) throw std::runtime_error("Missing Belgian second-tier relegation path");
    // All input, identity, calendar and conservation checks precede mutation.
    for (auto const& item:teams) comp(item.first)->AsLeague()->mTeams=item.second;
    top->mNumTeams=18; second->mNumTeams=15;
    top->mNumRelegatedTeams=2; second->mNumRelegatedTeams=2;
    top->mFirstSeasonMatchdays=topDates; top->mSecondSeasonMatchdays=topDates2;
    second->mFirstSeasonMatchdays=secondDates; second->mSecondSeasonMatchdays=secondDates2;
    top->mFixtures=BelgiumRoundRobin(18); second->mFixtures=BelgiumRoundRobin(15);
    top->mSuccessors.clear(); semi->mPredecessors={second->mID}; final->mSuccessors.clear();
    top->mInstructions.Clear(); top->mInstructions.PushBack(new FifamInstruction::GET_POOL(topPool->mID,0,18));
    second->mInstructions.Clear(); second->mInstructions.PushBack(new FifamInstruction::GET_POOL(secondPool->mID,0,15));
    semi->mInstructions.Clear();
    for (UInt position:{2u,3u,5u,4u}) semi->mInstructions.PushBack(new FifamInstruction::GET_TAB_X_TO_Y(second->mID,position,1));
    semi->mInstructions.PushBack(new FifamInstruction::GET_TAB_SPARE());
    topPool->mNumTeams=18; topPool->mReserveTeamsAllowed=false; topPool->mInstructions.Clear();
    topPool->mInstructions.PushBack(new FifamInstruction::GET_TAB_X_TO_Y(top->mID,1,16));
    topPool->mInstructions.PushBack(new FifamInstruction::GET_TAB_X_TO_Y(second->mID,1,1));
    topPool->mInstructions.PushBack(new FifamInstruction::GET_WINNER(final->mID));
    topPool->mInstructions.PushBack(new FifamInstruction::GET_TAB_SPARE());
    secondPool->mNumTeams=15; secondPool->mInstructions.Clear();
    secondPool->mInstructions.PushBack(new FifamInstruction::GET_LOSER(semi->mID));
    secondPool->mInstructions.PushBack(new FifamInstruction::GET_LOSER(final->mID));
    secondPool->mInstructions.PushBack(new FifamInstruction::GET_TAB_X_TO_Y(top->mID,17,2));
    secondPool->mInstructions.PushBack(new FifamInstruction::GET_TAB_X_TO_Y(second->mID,6,8));
    secondPool->mInstructions.PushBack(new FifamInstruction::GET_TAB_X_TO_Y(FifamCompID(117506051),1,1));
    secondPool->mInstructions.PushBack(new FifamInstruction::GET_TAB_X_TO_Y(FifamCompID(117964803),1,1));
    secondPool->mInstructions.PushBack(new FifamInstruction::GET_TAB_SPARE());
    relegationInput->mLeagueStartPosition=14;
    auto obsoleteID=obsolete->mID;
    db.mCompMap.erase(obsoleteID); delete obsolete;
    for (auto const& item:db.mCompMap) {
        auto p=item.second;
        if (std::find(p->mPredecessors.begin(),p->mPredecessors.end(),obsoleteID)!=p->mPredecessors.end() ||
            std::find(p->mSuccessors.begin(),p->mSuccessors.end(),obsoleteID)!=p->mSuccessors.end())
            throw std::runtime_error("Residual Belgian barrage dependency");
        p->mInstructions.ForAllCompetitionLinks([&](FifamCompID& id,UInt,FifamAbstractInstruction*) {
            if (id==obsoleteID) throw std::runtime_error("Residual Belgian barrage instruction");
        });
    }
    RequireValidLeagueSchedule(*top); RequireValidLeagueSchedule(*second);
    return {teams.size(),teams.size()+6};
}
