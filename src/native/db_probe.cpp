// Native bridge to FIFAM. Source is always read-only; staging writes are opt-in.
// Built against a locally cloned, pinned upstream. Never linked into Manager.exe.
#include "FifamDatabase.h"
#include "FifamPlayer.h"
#include "FifamPlayerLevel.h"
#include <Windows.h>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include "stage_plan.h"
#include "../../tests/native_stage_tests.h"
#include "../../tests/native_expired_tests.h"
#include "../../tests/native_successor_tests.h"
#include "../../tests/native_purchase_tests.h"

namespace fs = std::filesystem;

std::string utf8(std::wstring const& text) {
    if (text.empty()) return {};
    auto count = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text.data(),
        static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
    if (count <= 0) throw std::runtime_error("Invalid Unicode name");
    std::string result(static_cast<size_t>(count), '\0');
    WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text.data(),
        static_cast<int>(text.size()), result.data(), count, nullptr, nullptr);
    return result;
}

std::string csv(std::wstring const& text) {
    std::string result = "\"";
    for (char c : utf8(text)) { if (c == '"') result += '"'; result += c; }
    return result + '"';
}

#include "semantic_export.h"
#include "competition_inspection.h"
#include "league_membership_plan.h"
#include "rating_plan.h"
#include "rating_batch.h"
#include "staging_support.h"
#include "../../tests/native_semantic_tests.h"
#include "../../tests/native_world_tests.h"
#include "../../tests/native_global_tests.h"
#include "../../tests/native_competition_inspection_tests.h"
#include "../../tests/native_league_membership_tests.h"
#include "../../tests/native_rating_tests.h"
#include "../../tests/native_rating_batch_tests.h"

int wmain(int argc, wchar_t** argv) {
    try {
        if (argc==5 && std::wstring(argv[1])==L"--evaluate-rating-blocks") {
            EvaluateRatingBlocks(fs::canonical(argv[2]),fs::canonical(argv[3]),fs::weakly_canonical(argv[4]));
            return 0;
        }
        if (argc==3 && std::wstring(argv[1])==L"--self-test") {
            RunStagePlanTests(fs::weakly_canonical(argv[2]));
            RunExpiredLoanTests(fs::weakly_canonical(argv[2]));
            RunSuccessorLoanTests(fs::weakly_canonical(argv[2]));
            RunNativeSemanticTests(fs::weakly_canonical(argv[2]));
            RunNativeWorldTests(fs::weakly_canonical(argv[2]));
            RunNativeGlobalTests(fs::weakly_canonical(argv[2]));
            RunPurchaseLoanTests(fs::weakly_canonical(argv[2]));
            RunCompetitionInspectionTests(fs::weakly_canonical(argv[2]));
            RunLeagueMembershipTests(fs::weakly_canonical(argv[2]));
            RunRatingTests(fs::weakly_canonical(argv[2]));
            RunRatingBatchTests(fs::weakly_canonical(argv[2]));
            std::cout<<"NATIVE_STAGE_TESTS_PASS (see NATIVE_TESTS.json)\n";
            return 0;
        }
        const bool inspectPlan = argc == 5 && std::wstring(argv[3]) == L"--inspect-plan";
        const bool inspectCompetitions = argc == 4 && std::wstring(argv[3]) == L"--inspect-competitions";
        const bool stagePlan = argc == 5 && std::wstring(argv[3]) == L"--stage-plan";
        const bool stageLeagues = argc == 5 && std::wstring(argv[3]) == L"--stage-league-membership";
        const bool stageRatings = argc == 5 && std::wstring(argv[3]) == L"--stage-ratings";
        const bool previewRatings = argc == 5 && std::wstring(argv[3]) == L"--preview-ratings";
        const bool inspectRatings = argc == 4 && std::wstring(argv[3]) == L"--inspect-ratings";
        const bool stageWrite = stagePlan || stageLeagues || stageRatings || (argc == 4 && std::wstring(argv[3]) == L"--stage-roundtrip");
        if (argc != 3 && !stageWrite && !inspectPlan && !inspectCompetitions && !previewRatings && !inspectRatings)
            throw std::runtime_error("Usage: fm27-db-probe <database-dir> <new-external-output-dir> [--stage-roundtrip | --stage-plan <csv> | --stage-league-membership <csv> | --inspect-plan <csv> | --inspect-competitions | --inspect-ratings | --preview-ratings <csv> | --stage-ratings <csv>]");
        auto input = fs::canonical(argv[1]);
        auto output = fs::weakly_canonical(argv[2]);
        auto parent = input.parent_path().wstring();
        auto destination = output.wstring();
        std::transform(parent.begin(), parent.end(), parent.begin(), towlower);
        std::transform(destination.begin(), destination.end(), destination.begin(), towlower);
        if (destination == parent || destination.rfind(parent + L"\\", 0) == 0)
            throw std::runtime_error("Output must be outside the installation");
        if (fs::exists(output)) throw std::runtime_error("Output directory already exists");
        if (!fs::is_regular_file(input / "Countries.sav")) throw std::runtime_error("Countries.sav missing");
        // The installed product is based on FM13. Loading data does not grant
        // executable compatibility for any runtime patch.
        auto db = std::make_unique<FifamDatabase>(13, input);
        if (inspectRatings) {
            fs::create_directories(output);
            ExportRatingInspection(*db,output/"native_ratings.csv");
            std::cout<<"READ_ONLY_RATING_INSPECTION_OK players="<<db->mPlayers.size()<<'\n';
            return 0;
        }
        if (inspectCompetitions) {
            fs::create_directories(output);
            ExportCompetitionInspection(*db,output);
            std::cout<<"READ_ONLY_COMPETITION_INSPECTION_OK competitions="<<db->mCompMap.size()<<'\n';
            return 0;
        }
        StagePlanResult planResult{};
        LeagueMembershipResult leagueResult{};
        RatingPlanResult ratingResult{};
        if (stageRatings || previewRatings) {
            fs::create_directories(output/"before-ratings");
            ExportPlayerSemantics(*db,output/"before-ratings"/"native_player_semantics.csv");
            ExportRatingInspection(*db,output/"before-ratings"/"native_ratings.csv");
            ratingResult=ApplyRatingPlan(*db,argv[4],previewRatings);
            std::cout<<"RATING_PLAYERS="<<ratingResult.players<<" ATTRIBUTES="<<ratingResult.attributes<<'\n';
        }
        if (stageLeagues) leagueResult=ApplyLeagueMembershipPlan(*db,argv[4]);
        if (inspectPlan) {
            fs::create_directories(output/"before-plan");
            ExportPlayerSemantics(*db,output/"before-plan"/"native_player_semantics.csv");
        }
        if (stagePlan || inspectPlan) {
            planResult=ApplyStagePlan(*db,argv[4]);
            std::cout << "STAGED_SQUAD_ROWS=" << planResult.rows << '\n';
        }
        fs::create_directories(output);
        ExportPlayerSemantics(*db,output/"native_player_semantics.csv");
        ExportRatingInspection(*db,output/"native_ratings.csv");
        std::ofstream records(output / "native_players.csv", std::ios::binary);
        if (!records) throw std::runtime_error("Cannot create native projection");
        records << "fm_id,fifa_id,club_id,name,dob,main_position,style,level13,best_style,level13_best_style\n";
        std::vector<FifamPlayer*> ordered(db->mPlayers.begin(), db->mPlayers.end());
        std::sort(ordered.begin(), ordered.end(), [](auto a, auto b) { return a->mID < b->mID; });
        for (auto p : ordered) {
            auto best = FifamPlayerLevel::GetBestStyleForPlayer(p);
            records << p->mID << ',' << p->mFifaID << ',' << (p->mClub ? p->mClub->mUniqueID : 0) << ','
                << csv(p->GetName()) << ',' << p->mBirthday.ToStringA() << ','
                << csv(p->mMainPosition.ToStr()) << ',' << csv(p->mPlayingStyle.ToStr()) << ','
                << static_cast<unsigned>(FifamPlayerLevel::GetPlayerLevel13(p, p->mMainPosition, p->mPlayingStyle)) << ','
                << csv(best.ToStr()) << ','
                << static_cast<unsigned>(FifamPlayerLevel::GetPlayerLevel13(p, p->mMainPosition, best)) << '\n';
        }
        records.flush();
        if (!records) throw std::runtime_error("Native export write failed");
        std::cout << "READ_ONLY_OK players=" << db->mPlayers.size() << " clubs=" << db->mClubs.size() << '\n';
        if (stageWrite) {
            // Canonical writer after only the explicitly selected plan. The
            // external output tree was checked above and must not pre-exist.
            // Generated data is for round-trip tests, never a release artifact.
            db->Write(13, FifamVersion(0x2013, 0x12), output / "database");
            WriteExactPlayerRelations(*db,output/"database"/"PlayerRelations.sav");
            PreserveNativeSupport(input,output);
            std::ofstream marker(output / "STAGING_ONLY.txt");
            marker << ((stagePlan || stageLeagues || stageRatings) ? "MODIFIED_CANDIDATE_NOT_GAME_VALIDATED\n" : "UNMODIFIED_NATIVE_REWRITE_REQUIRES_SEMANTIC_VALIDATION\n");
            marker.flush();
            if (!marker) throw std::runtime_error("Cannot write staging status");
            SYSTEMTIME captured{};
            GetSystemTime(&captured);
            std::ofstream manifest(output / "DATABASE_METADATA.txt");
            if (stagePlan) manifest << "DATABASE_SNAPSHOT_DATE=" << planResult.snapshot << '\n';
            if (stageRatings) manifest<<"DATABASE_SNAPSHOT_DATE="<<ratingResult.snapshot<<'\n'
                <<"RATING_CHANGED_PLAYERS="<<ratingResult.players<<'\n'
                <<"RATING_CHANGED_ATTRIBUTES="<<ratingResult.attributes<<'\n';
            if (stageLeagues) {
                manifest << "DATABASE_SNAPSHOT_DATE="<<leagueResult.snapshot<<'\n'
                    <<"LEAGUE_MEMBERSHIP_COMPETITIONS="<<leagueResult.leagues<<'\n'
                    <<"LEAGUE_MEMBERSHIP_CHANGED_SLOTS="<<leagueResult.changedSlots<<'\n';
            }
            manifest << "BUILD_CAPTURE_DATE=" << captured.wYear << '-';
            if (captured.wMonth < 10) manifest << '0';
            manifest << captured.wMonth << '-';
            if (captured.wDay < 10) manifest << '0';
            manifest << captured.wDay << '\n'
                << (stageRatings ? "SNAPSHOT_KIND=RATING_CANDIDATE_CALIBRATION_AND_GAME_GATES_OPEN\n" :
                    stagePlan ? "SNAPSHOT_KIND=PARTIAL_CURRENT_SQUAD_CANDIDATE\n" : stageLeagues ?
                    "SNAPSHOT_KIND=LEAGUE_MEMBERSHIP_CANDIDATE_FORMAT_AND_GAME_GATES_OPEN\n" :
                    "SNAPSHOT_KIND=INSTALLED_BASELINE_CAPTURE_NOT_UPDATED_2026_27_SQUADS\n")
                << "STATUS=STAGING_ONLY_REQUIRES_FULL_VALIDATION\n";
            manifest.flush();
            if (!manifest) throw std::runtime_error("Cannot write database metadata");
            std::cout << "STAGING_WRITE_COMPLETED_NOT_VALIDATED\n";
        }
        return 0;
    } catch (std::exception const& error) {
        std::cerr << "NATIVE_PROBE_FAILED: " << error.what() << '\n';
        return 1;
    }
}
