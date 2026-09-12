#pragma once
#include "belgium_format_plan.h"

// Scoped GER3 membership plus the necessary Bayern19 native format. Untouched
// lower memberships remain baseline data, not claims of global2026 coverage.
inline size_t ApplyGermany2026Membership(FifamDatabase& db,std::filesystem::path const& path) {
    auto comp=[&](UInt id) {
        auto p=db.GetCompetition(FifamCompID(id));
        if (!p) throw std::runtime_error("Missing German format dependency");
        return p;
    };
    auto bayern=comp(352387079)->AsLeague();
    auto donor=comp(352387086)->AsLeague();
    auto pool=comp(353894403)->AsPool();
    if (!bayern || !donor || !pool || bayern->mNumTeams!=18 || bayern->mTeams.size()!=18 ||
        bayern->mNumRounds!=2 || pool->mNumTeams!=90 || donor->mNumTeams!=19 || donor->mNumRounds!=2)
        throw std::runtime_error("German format baseline differs");
    RequireValidLeagueSchedule(*bayern);RequireValidLeagueSchedule(*donor);
    FifamInstruction::GET_POOL* allocation=nullptr;
    bayern->mInstructions.ForAll([&](FifamAbstractInstruction* instruction) {
        auto p=dynamic_cast<FifamInstruction::GET_POOL*>(instruction);
        if (!p || allocation || p->mPool!=pool->mID || p->mPoolStartPosition!=72 || p->mNumTeams!=18)
            throw std::runtime_error("German Bayern pool allocation differs");
        allocation=p;
    });
    if (!allocation) throw std::runtime_error("Missing Bayern pool allocation");
    struct InstructionDelta { FifamInstruction::GET_TAB_X_TO_Y* p;UInt start,count; };
    std::vector<InstructionDelta> instructions;
    for (auto const& item:db.mCompMap) item.second->mInstructions.ForAll([&](FifamAbstractInstruction* instruction) {
        auto p=dynamic_cast<FifamInstruction::GET_TAB_X_TO_Y*>(instruction);
        if (!p || p->mLeague!=bayern->mID) return;
        UInt id=item.second->mID.ToInt();
        if (id==352845829 && p->mNumTeams==1 && (p->mLeagueStartPosition==15 || p->mLeagueStartPosition==16))
            instructions.push_back({p,p->mLeagueStartPosition+1,1});
        else if (id==353894403 && p->mLeagueStartPosition==2 && p->mNumTeams==13)
            instructions.push_back({p,2,14});
        else if (id==353894404 && p->mLeagueStartPosition==17 && p->mNumTeams==2)
            instructions.push_back({p,18,2});
        else throw std::runtime_error("Unexpected Bayern table dependency");
    });
    if (instructions.size()!=4) throw std::runtime_error("Incomplete Bayern table dependencies");
    using TeamKey=std::pair<UInt,UChar>;
    std::map<UInt,Vector<FifamClubLink>> teams;
    std::set<TeamKey> proposed,boundary;
    std::ifstream input(path,std::ios::binary);std::string line;
    if (!input || !std::getline(input,line)) throw std::runtime_error("Missing German membership plan");
    if (line.rfind("\xEF\xBB\xBF",0)==0) line.erase(0,3);
    if (PlanCsv(line)!=std::vector<std::string>{"competition_id","club_id","team_type"})
        throw std::runtime_error("Invalid German membership schema");
    while (std::getline(input,line)) {
        if (line.empty() || line=="\r") continue;
        auto row=PlanCsv(line);if (row.size()!=3) throw std::runtime_error("Invalid German membership row");
        UInt id=PlanUInt(row[0]),uid=PlanUInt(row[1]);auto club=db.GetClubFromUID(uid,false);
        if (!club || !club->mCountry || club->mCountry->mId!=21 || (row[2]!="FIRST" && row[2]!="RESERVE"))
            throw std::runtime_error("Invalid German club identity");
        auto type=row[2]=="FIRST"?FifamClubTeamType(FifamClubTeamType::First):FifamClubTeamType(FifamClubTeamType::Reserve);
        TeamKey key{uid,type.ToInt()};
        if (!id) {
            if (!boundary.insert(key).second) throw std::runtime_error("Duplicate German boundary");
            continue;
        }
        auto league=comp(id)->AsLeague();
        if (!league || id<352387074 || id>352387093 || league->mID.mType!=FifamCompType::League)
            throw std::runtime_error("German plan exceeds scoped dependency leagues");
        if (!proposed.insert(key).second) throw std::runtime_error("Duplicate German proposed club");
        teams[id].push_back(FifamClubLink(club,type));
    }
    if (teams[352387074].size()!=20 || teams[352387079].size()!=19)
        throw std::runtime_error("German plan requires complete GER3 and Bayern19");
    std::map<TeamKey,size_t> before,after;
    std::map<TeamKey,UInt> beforeLeague,afterLeague;
    for (auto const& item:db.mCompMap) {
        auto league=item.second->AsLeague();
        if (!league || league->mID.mRegion.ToInt()!=21 || league->mID.mType!=FifamCompType::League) continue;
        auto id=league->mID.ToInt();auto replacement=teams.find(id);
        if (replacement!=teams.end() && id!=352387079 && replacement->second.size()!=league->mNumTeams)
            throw std::runtime_error("Unreviewed German league-size change");
        for (auto const& link:league->mTeams) if (link.mPtr) {
            TeamKey key{link.mPtr->mUniqueID,link.mTeamType.ToInt()};++before[key];beforeLeague[key]=id;
        }
        for (auto const& link:replacement==teams.end()?league->mTeams:replacement->second) if (link.mPtr) {
            TeamKey key{link.mPtr->mUniqueID,link.mTeamType.ToInt()};++after[key];afterLeague[key]=id;
        }
    }
    auto lowest=[](UInt id){return id>=352387080 && id<=352387093;};
    for (auto const& key:boundary) {
        size_t a=before.count(key)?before.at(key):0,b=after.count(key)?after.at(key):0;
        bool enters=a==0 && b==1 && lowest(afterLeague.at(key));
        bool leaves=a==1 && b==0 && lowest(beforeLeague.at(key));
        if (!enters && !leaves) throw std::runtime_error("German boundary does not cross the lowest modeled tier");
    }
    auto conservedBefore=before,conservedAfter=after;
    for (auto const& key:boundary) {conservedBefore.erase(key);conservedAfter.erase(key);}
    if (conservedBefore!=conservedAfter) throw std::runtime_error("Undeclared German club loss or creation");
    for (auto const& item:after) if (item.second!=1) throw std::runtime_error("Duplicate German domestic membership");
    // All guarded memberships and script expectations precede mutation.
    for (auto const& item:teams) comp(item.first)->AsLeague()->mTeams=item.second;
    bayern->mNumTeams=19;bayern->mFixtures=BelgiumRoundRobin(19);
    bayern->mFirstSeasonMatchdays=donor->mFirstSeasonMatchdays;
    bayern->mSecondSeasonMatchdays=donor->mSecondSeasonMatchdays;
    allocation->mNumTeams=19;pool->mNumTeams=91;
    for (auto& delta:instructions) {delta.p->mLeagueStartPosition=delta.start;delta.p->mNumTeams=delta.count;}
    RequireValidLeagueSchedule(*bayern);
    return teams.size()+3;
}
