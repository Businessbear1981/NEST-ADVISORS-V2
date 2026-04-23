// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title NestLedger
 * @dev Immutable audit trail for NEST Capital Partners deal events.
 *      Arden Edge Capital x Soparrow Capital
 */
contract NestLedger {
    address public owner;

    uint256 public totalDeals;
    uint256 public totalRefiCycles;
    uint256 public totalFeesCaptured;
    uint256 public totalEquityPositions;

    // Events
    event DealRecorded(bytes32 indexed dealHash, string dealId, uint256 timestamp);
    event RefiCycleExecuted(bytes32 indexed dealHash, uint256 cycle, uint256 oldRate, uint256 newRate, uint256 feeCaptured);
    event EquityPositionRecorded(bytes32 indexed companyHash, string companyName, uint256 entryEv, uint256 equityPct);
    event LenderMatchRecorded(bytes32 indexed dealHash, string lenderId, uint256 matchScore);
    event MAAnalysisRecorded(bytes32 indexed companyHash, string companyName, string level);
    event InvestorAllocation(bytes32 indexed dealHash, string investorId, uint256 amount, string tranche);
    event CovenantTest(bytes32 indexed dealHash, string metric, uint256 value, uint256 threshold, bool passed);
    event MarketplaceListing(bytes32 indexed dealHash, string dealId, uint256 timestamp);
    event CallTriggered(bytes32 indexed dealHash, uint256 oldBps, uint256 newBps, uint256 feeUsd);
    event PutAlert(bytes32 indexed dealHash, uint256 rateRiseBps, string apexAction);
    event NestEvent(bytes32 indexed dealHash, string eventType, bytes data);

    // Storage
    struct Deal {
        string dealId;
        bytes32 dataHash;
        uint256 timestamp;
        bool exists;
    }

    mapping(bytes32 => Deal) public deals;
    mapping(bytes32 => uint256[]) public refiCycles;

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function recordDeal(string calldata dealId, bytes32 dataHash) external onlyOwner {
        bytes32 dealHash = keccak256(abi.encodePacked(dealId));
        deals[dealHash] = Deal(dealId, dataHash, block.timestamp, true);
        totalDeals++;
        emit DealRecorded(dealHash, dealId, block.timestamp);
    }

    function executeRefiCycle(
        string calldata dealId,
        uint256 cycle,
        uint256 oldRate,
        uint256 newRate,
        uint256 feeCaptured
    ) external onlyOwner {
        bytes32 dealHash = keccak256(abi.encodePacked(dealId));
        refiCycles[dealHash].push(cycle);
        totalRefiCycles++;
        totalFeesCaptured += feeCaptured;
        emit RefiCycleExecuted(dealHash, cycle, oldRate, newRate, feeCaptured);
    }

    function recordEquityPosition(
        string calldata companyName,
        uint256 entryEv,
        uint256 equityPct,
        bytes calldata warrantTerms
    ) external onlyOwner {
        bytes32 companyHash = keccak256(abi.encodePacked(companyName));
        totalEquityPositions++;
        emit EquityPositionRecorded(companyHash, companyName, entryEv, equityPct);
        emit NestEvent(companyHash, "EQUITY_POSITION", warrantTerms);
    }

    function recordLenderMatch(
        string calldata dealId,
        string calldata lenderId,
        uint256 matchScore
    ) external onlyOwner {
        bytes32 dealHash = keccak256(abi.encodePacked(dealId));
        emit LenderMatchRecorded(dealHash, lenderId, matchScore);
    }

    function recordMAAnalysis(
        string calldata companyName,
        string calldata level,
        bytes calldata analysisData
    ) external onlyOwner {
        bytes32 companyHash = keccak256(abi.encodePacked(companyName));
        emit MAAnalysisRecorded(companyHash, companyName, level);
        emit NestEvent(companyHash, "MA_ANALYSIS", analysisData);
    }

    function recordInvestorAllocation(
        string calldata dealId,
        string calldata investorId,
        uint256 amount,
        string calldata tranche
    ) external onlyOwner {
        bytes32 dealHash = keccak256(abi.encodePacked(dealId));
        emit InvestorAllocation(dealHash, investorId, amount, tranche);
    }

    function recordCovenantTest(
        string calldata dealId,
        string calldata metric,
        uint256 value,
        uint256 threshold
    ) external onlyOwner {
        bytes32 dealHash = keccak256(abi.encodePacked(dealId));
        bool passed = value >= threshold;
        emit CovenantTest(dealHash, metric, value, threshold, passed);
    }

    function createMarketplaceListing(
        string calldata dealId,
        bytes calldata listingData
    ) external onlyOwner {
        bytes32 dealHash = keccak256(abi.encodePacked(dealId));
        emit MarketplaceListing(dealHash, dealId, block.timestamp);
        emit NestEvent(dealHash, "MARKETPLACE_LISTING", listingData);
    }

    function recordCallTrigger(
        string calldata dealId,
        uint256 oldBps,
        uint256 newBps,
        uint256 feeUsd
    ) external onlyOwner {
        bytes32 dealHash = keccak256(abi.encodePacked(dealId));
        totalFeesCaptured += feeUsd;
        emit CallTriggered(dealHash, oldBps, newBps, feeUsd);
    }

    function recordPutAlert(
        string calldata dealId,
        uint256 rateRiseBps,
        string calldata apexAction
    ) external onlyOwner {
        bytes32 dealHash = keccak256(abi.encodePacked(dealId));
        emit PutAlert(dealHash, rateRiseBps, apexAction);
    }

    // View functions
    function getDeal(string calldata dealId) external view returns (Deal memory) {
        bytes32 dealHash = keccak256(abi.encodePacked(dealId));
        return deals[dealHash];
    }

    function getRefiCycles(string calldata dealId) external view returns (uint256[] memory) {
        bytes32 dealHash = keccak256(abi.encodePacked(dealId));
        return refiCycles[dealHash];
    }

    function getPlatformStats() external view returns (
        uint256 _totalDeals,
        uint256 _totalRefiCycles,
        uint256 _totalFeesCaptured,
        uint256 _totalEquityPositions
    ) {
        return (totalDeals, totalRefiCycles, totalFeesCaptured, totalEquityPositions);
    }
}
