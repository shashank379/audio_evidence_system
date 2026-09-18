// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract AudioEvidence {
    struct EvidenceRecord {
        string caseId;
        string audioHash;
        string metadata;
        uint256 timestamp;
        address submitter;
        bool exists;
    }
    
    struct AnalysisRecord {
        string caseId;
        string tamperResult;
        string speakerResult;
        uint256 timestamp;
        bool exists;
    }
    
    mapping(string => EvidenceRecord) public evidenceRecords;
    mapping(string => AnalysisRecord) public analysisRecords;
    
    event EvidenceStored(string indexed caseId, string audioHash, uint256 timestamp);
    event AnalysisStored(string indexed caseId, string results, uint256 timestamp);
    
    function storeAudioEvidence(
        string memory _caseId,
        string memory _audioHash,
        string memory _metadata
    ) public {
        require(bytes(_caseId).length > 0, "Case ID cannot be empty");
        require(bytes(_audioHash).length > 0, "Audio hash cannot be empty");
        
        evidenceRecords[_caseId] = EvidenceRecord({
            caseId: _caseId,
            audioHash: _audioHash,
            metadata: _metadata,
            timestamp: block.timestamp,
            submitter: msg.sender,
            exists: true
        });
        
        emit EvidenceStored(_caseId, _audioHash, block.timestamp);
    }
    
    function storeAnalysisResults(
        string memory _caseId,
        string memory _results
    ) public {
        require(evidenceRecords[_caseId].exists, "Evidence record must exist first");
        
        analysisRecords[_caseId] = AnalysisRecord({
            caseId: _caseId,
            tamperResult: _results,
            speakerResult: _results,
            timestamp: block.timestamp,
            exists: true
        });
        
        emit AnalysisStored(_caseId, _results, block.timestamp);
    }
    
    function getEvidenceRecord(string memory _caseId) 
        public view returns (
            string memory caseId,
            string memory audioHash,
            string memory metadata,
            uint256 timestamp,
            address submitter
        ) {
        EvidenceRecord memory record = evidenceRecords[_caseId];
        require(record.exists, "Evidence record does not exist");
        
        return (
            record.caseId,
            record.audioHash,
            record.metadata,
            record.timestamp,
            record.submitter
        );
    }
    
    function getAnalysisRecord(string memory _caseId)
        public view returns (
            string memory caseId,
            string memory tamperResult,
            string memory speakerResult,
            uint256 timestamp
        ) {
        AnalysisRecord memory record = analysisRecords[_caseId];
        require(record.exists, "Analysis record does not exist");
        
        return (
            record.caseId,
            record.tamperResult,
            record.speakerResult,
            record.timestamp
        );
    }
}