#pragma once
#include "FifamCompLeague.h"
#include "FifamCompPool.h"

// Read the actual native graph and calendars before planning competition edits.
// This mode neither writes a database nor changes competition instructions.
inline void ExportCompetitionInspection(FifamDatabase& db, std::filesystem::path const& output) {
    std::ofstream competitions(output/"competition_structure.csv",std::ios::binary);
    std::ofstream members(output/"competition_members.csv",std::ios::binary);
    std::ofstream calendars(output/"competition_calendars.csv",std::ios::binary);
    std::ofstream fixtures(output/"competition_fixtures.csv",std::ios::binary);
    std::ofstream edges(output/"competition_edges.csv",std::ios::binary);
    std::ofstream instructions(output/"competition_instructions.csv",std::ios::binary);
    competitions<<"competition_id,db_type,num_teams,competition_level,league_level,rounds,relegated_teams,name\n";
    members<<"competition_id,slot,club_id,team_type\n";
    calendars<<"competition_id,season,index,day\n";
    fixtures<<"competition_id,matchday,match,home_slot,away_slot\n";
    edges<<"competition_id,relation,index,target_competition_id,target_exists\n";
    instructions<<"competition_id,index,instruction_id,native_serialization\n";
    size_t edgeCount=0, missingCount=0, instructionCount=0, memberCount=0;
    for (auto const& entry:db.mCompMap) {
        auto comp=entry.second;
        auto id=comp->mID.ToInt();
        auto league=comp->AsLeague();
        competitions<<id<<','<<csv(comp->GetDbType().ToStr())<<','<<comp->mNumTeams<<','
            <<static_cast<unsigned>(comp->mCompetitionLevel)<<',';
        if (league) competitions<<static_cast<unsigned>(league->mLeagueLevel)<<','
            <<static_cast<unsigned>(league->mNumRounds)<<','<<static_cast<unsigned>(league->mNumRelegatedTeams);
        else competitions<<",,";
        competitions<<','<<csv(comp->GetName())<<'\n';
        auto link=[&](char const* kind,UInt index,FifamCompID const& target) {
            const bool exists=db.GetCompetition(target)!=nullptr;
            edges<<id<<','<<kind<<','<<index<<','<<target.ToInt()<<','<<(exists?1:0)<<'\n';
            ++edgeCount; if (!exists) ++missingCount;
        };
        for (UInt i=0;i<comp->mPredecessors.size();++i) link("PREDECESSOR",i,comp->mPredecessors[i]);
        for (UInt i=0;i<comp->mSuccessors.size();++i) link("SUCCESSOR",i,comp->mSuccessors[i]);
        if (auto pool=comp->AsPool())
            for (UInt i=0;i<pool->mCompConstraints.size();++i) link("POOL_CONSTRAINT",i,pool->mCompConstraints[i]);
        comp->mInstructions.ForAllCompetitionLinks([&](FifamCompID& target,UInt index,FifamAbstractInstruction*) {
            link("INSTRUCTION",index,target);
        });
        FifamNation nation;
        if (comp->mID.mRegion.ToInt()>0 && comp->mID.mRegion.ToInt()<=FifamDatabase::NUM_COUNTRIES)
            nation.SetFromInt(comp->mID.mRegion.ToInt());
        comp->mInstructions.ForAll([&](FifamAbstractInstruction* instruction,UInt index) {
            FifamInstructionsList copy;
            copy.PushBack(instruction->Clone());
            std::wstring serialized;
            { FifamWriter writer(&serialized,13,FifamVersion(0x2013,0x12));
              copy.Write(writer,&db,comp->GetDbType(),nation); }
            instructions<<id<<','<<index<<','<<csv(instruction->GetID().ToStr())<<','<<csv(serialized)<<'\n';
            ++instructionCount;
        });
        if (!league) continue;
        for (UInt i=0;i<league->mTeams.size();++i) {
            auto const& team=league->mTeams[i];
            members<<id<<','<<(i+1)<<','<<(team.mPtr?team.mPtr->mUniqueID:0)<<','<<csv(team.mTeamType.ToStr())<<'\n';
            ++memberCount;
        }
        for (UInt i=0;i<league->mFirstSeasonMatchdays.size();++i)
            calendars<<id<<",1,"<<(i+1)<<','<<league->mFirstSeasonMatchdays[i]<<'\n';
        for (UInt i=0;i<league->mSecondSeasonMatchdays.size();++i)
            calendars<<id<<",2,"<<(i+1)<<','<<league->mSecondSeasonMatchdays[i]<<'\n';
        for (UInt day=0;day<league->mFixtures.size();++day)
            for (UInt match=0;match<league->mFixtures[day].size();++match) {
                auto const& pair=league->mFixtures[day][match];
                fixtures<<id<<','<<(day+1)<<','<<(match+1)<<','<<static_cast<unsigned>(pair.first)
                    <<','<<static_cast<unsigned>(pair.second)<<'\n';
            }
    }
    for (auto stream:{&competitions,&members,&calendars,&fixtures,&edges,&instructions}) {
        stream->flush(); if (!*stream) throw std::runtime_error("Competition inspection export failed");
    }
    std::ofstream metadata(output/"COMPETITION_INSPECTION.json");
    metadata<<"{\"status\":\"READ_ONLY_NATIVE_INSPECTION\",\"competitions\":"<<db.mCompMap.size()
        <<",\"edges\":"<<edgeCount<<",\"unresolved_edge_targets\":"<<missingCount
        <<",\"instructions\":"<<instructionCount<<",\"league_members\":"<<memberCount
        <<",\"database_writes\":0,\"limitations\":\"Instruction text uses native serializer on clones; edge targets are inspected separately even when native serialization disables an instruction. No membership, format, calendar or game validation claim.\"}\n";
    metadata.flush(); if (!metadata) throw std::runtime_error("Competition inspection metadata failed");
}
