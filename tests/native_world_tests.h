#pragma once

inline void RunNativeWorldTests(std::filesystem::path const& output) {
    FifamDatabase db;
    auto country=db.CreateCountry(14);
    auto club=db.CreateClub(country); club->mUniqueID=917505; db.AddClubToMap(club);
    auto other=db.CreateClub(country); other->mUniqueID=917506; db.AddClubToMap(other);
    auto p=db.CreatePlayer(club,1); p->mFirstName=L"Captain"; p->mBirthday=FifamDate(1,1,2000);
    auto q=db.CreatePlayer(club,2); q->mFirstName=L"Deputy"; q->mBirthday=FifamDate(2,1,2000);
    auto staff=db.CreateStaff(nullptr,3); staff->mFirstName=L"Coach"; staff->mLinkedCountry=FifamNation::England;
    club->mCaptains={p,q,nullptr}; club->mPartnershipClub=FifamClubLink(other);
    auto content=[](std::filesystem::path const& path) {
        std::ifstream file(path,std::ios::binary);
        return std::string(std::istreambuf_iterator<char>(file),std::istreambuf_iterator<char>());
    };
    auto exportTo=[&](char const* name) {
        auto dir=output/name; std::filesystem::create_directories(dir);
        ExportPlayerSemantics(db,dir/"native_player_semantics.csv"); return dir;
    };
    auto first=exportTo("world-original");
    club->SetWriteableID(543); other->SetWriteableID(321); other->SetIsWriteable(false);
    p->mID=902; q->mID=901; // Native IDs may change on reread; person identity does not.
    auto normalized=exportTo("world-normalized");
    for (auto const* name:{"native_world_clubs.csv","native_world_countries.csv","native_world_person_links.csv"})
        if (content(first/name)!=content(normalized/name)) throw std::runtime_error("World identity normalization failed");
    if (club->GetWriteableID()!=543 || other->GetIsWriteable() || country->mNumWriteableLeagueLevels!=0 ||
        db.mStaffs!=Set<FifamStaff*>{staff} || club->mPlayers!=Vector<FifamPlayer*>{p,q} || club->mCaptains[0]!=p)
        throw std::runtime_error("World inspection mutated source state");
    other->SetIsWriteable(true);
    if (other->GetWriteableID()!=321) throw std::runtime_error("World inspection lost hidden club ID");
    other->SetIsWriteable(false);
    ++club->mStadiumSeatsCapacity;
    auto stadium=exportTo("world-stadium");
    if (content(stadium/"native_world_clubs.csv")==content(normalized/"native_world_clubs.csv"))
        throw std::runtime_error("Stadium mutation not detected");
    ++country->mYearsForNaturalization;
    auto rules=exportTo("world-rules");
    if (content(rules/"native_world_countries.csv")==content(stadium/"native_world_countries.csv"))
        throw std::runtime_error("Country rule mutation not detected");
    std::swap(club->mCaptains[0],club->mCaptains[1]);
    auto captain=exportTo("world-captain");
    if (content(captain/"native_world_person_links.csv")==content(rules/"native_world_person_links.csv"))
        throw std::runtime_error("Captain slot mutation not detected");
    std::swap(club->mPlayers[0],club->mPlayers[1]);
    auto order=exportTo("world-member-order");
    if (content(order/"native_world_person_links.csv")==content(captain/"native_world_person_links.csv"))
        throw std::runtime_error("Member order mutation not detected");
    auto failed=output/"world-failure";
    std::filesystem::create_directories(failed/"native_world_countries.csv");
    bool rejected=false;
    try { ExportPlayerSemantics(db,failed/"native_player_semantics.csv"); }
    catch (std::runtime_error const&) { rejected=true; }
    if (!rejected || db.mStaffs!=Set<FifamStaff*>{staff} || other->GetIsWriteable() || club->GetWriteableID()!=543)
        throw std::runtime_error("Failed world export did not restore source state");
    std::ofstream report(output/"NATIVE_TESTS.json");
    report<<"{\"status\":\"PASS\",\"tests\":50,\"scope\":\"44 staging, loan, semantic and support cases; 6 world cases: ID normalization and state preservation, stadium, country rules, captain slots, member ordering, restoration on failure\"}\n";
}
