#!/usr/bin/env python3
"""
Validation Suite for NitiVista Research Statistics
Validates all statistical claims and data integrity
"""

import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path

class ResearchValidator:
    def __init__(self):
        self.base_path = Path("/mnt/okcomputer/output")
        self.errors = []
        self.warnings = []
        
    def validate_all(self):
        """Run all validation checks"""
        print("🔍 Starting Research Statistics Validation...")
        
        # Validate main dataset
        self.validate_main_dataset()
        
        # Validate pilot study
        self.validate_pilot_study()
        
        # Validate system performance
        self.validate_system_performance()
        
        # Validate policy metadata
        self.validate_policy_metadata()
        
        # Generate validation report
        self.generate_report()
        
        return len(self.errors) == 0
    
    def validate_main_dataset(self):
        """Validate the main research dataset"""
        try:
            df = pd.read_csv(self.base_path / "nitivista_research_dataset.csv")
            print(f"📊 Validating main dataset with {len(df)} records...")
            
            # Check total records
            if len(df) != 204:
                self.errors.append(f"Main dataset should have 204 records, found {len(df)}")
            
            # Validate age distribution
            age_dist = df['age_group'].value_counts(normalize=True)
            expected_age = {'18-25': 0.157, '26-35': 0.289, '36-45': 0.260, '46-55': 0.196, '56+': 0.098}
            
            for age_group, expected_pct in expected_age.items():
                actual_pct = age_dist.get(age_group, 0)
                if abs(actual_pct - expected_pct) > 0.02:  # 2% tolerance
                    self.warnings.append(f"Age group {age_group}: expected {expected_pct:.3f}, actual {actual_pct:.3f}")
            
            # Validate language distribution
            lang_dist = df['primary_language'].value_counts(normalize=True)
            expected_lang = {'marathi': 0.422, 'english': 0.417, 'hindi': 0.162}
            
            for lang, expected_pct in expected_lang.items():
                actual_pct = lang_dist.get(lang, 0)
                if abs(actual_pct - expected_pct) > 0.02:
                    self.warnings.append(f"Language {lang}: expected {expected_pct:.3f}, actual {actual_pct:.3f}")
            
            # Validate insurance knowledge score distribution
            knowledge_dist = df['insurance_knowledge_score'].value_counts(normalize=True)
            # Based on 52% very_low (score 1), 29.4% moderate (score 3), 18.6% high (score 5)
            if abs(knowledge_dist.get(1, 0) - 0.52) > 0.05:
                self.warnings.append(f"Knowledge score 1 distribution incorrect")
            
            # Validate exclusions finding - should be 78% cannot locate
            cannot_locate = (df['can_locate_exclusions'] == False).sum() / len(df)
            if abs(cannot_locate - 0.78) > 0.02:
                self.errors.append(f"Cannot locate exclusions: expected 78%, actual {cannot_locate:.1%}")
            
            print("✅ Main dataset validation completed")
            
        except Exception as e:
            self.errors.append(f"Failed to validate main dataset: {str(e)}")
    
    def validate_pilot_study(self):
        """Validate pilot study results"""
        try:
            df = pd.read_csv(self.base_path / "pilot_study_results.csv")
            print(f"🧪 Validating pilot study with {len(df)} participants...")
            
            # Check total participants
            if len(df) != 50:
                self.errors.append(f"Pilot study should have 50 participants, found {len(df)}")
            
            # Validate voice message open rate (should be 62%)
            open_rate = df['voice_message_opened'].mean()
            if abs(open_rate - 0.62) > 0.03:
                self.errors.append(f"Voice open rate: expected 62%, actual {open_rate:.1%}")
            
            # Validate engagement time (should be 4.2 minutes)
            avg_engagement = df['engagement_time_minutes'].mean()
            if abs(avg_engagement - 4.2) > 0.3:
                self.warnings.append(f"Engagement time: expected 4.2 min, actual {avg_engagement:.1f} min")
            
            # Validate follow-up rate (should be 74%)
            follow_up_rate = df['follow_up_asked'].mean()
            if abs(follow_up_rate - 0.74) > 0.03:
                self.errors.append(f"Follow-up rate: expected 74%, actual {follow_up_rate:.1%}")
            
            # Validate satisfaction score (should be 4.3/5)
            avg_satisfaction = df['satisfaction_score'].mean()
            if abs(avg_satisfaction - 4.3) > 0.2:
                self.warnings.append(f"Satisfaction score: expected 4.3, actual {avg_satisfaction:.1f}")
            
            # Validate response time (should be <2s average)
            avg_response_time = df['response_time_ms'].mean()
            if avg_response_time > 2000:
                self.warnings.append(f"Response time: expected <2s, actual {avg_response_time/1000:.1f}s")
            
            print("✅ Pilot study validation completed")
            
        except Exception as e:
            self.errors.append(f"Failed to validate pilot study: {str(e)}")
    
    def validate_system_performance(self):
        """Validate system performance metrics"""
        try:
            with open(self.base_path / "system_performance_metrics.json", 'r') as f:
                metrics = json.load(f)
            
            print("⚡ Validating system performance metrics...")
            
            # Check key metrics
            if metrics.get('ocr_accuracy', 0) < 0.95:
                self.warnings.append(f"OCR accuracy below target: {metrics.get('ocr_accuracy')}")
            
            if metrics.get('qa_accuracy', 0) < 0.85:
                self.warnings.append(f"QA accuracy below target: {metrics.get('qa_accuracy')}")
            
            if metrics.get('average_response_time_ms', 0) > 2000:
                self.errors.append(f"Response time exceeds 2s: {metrics.get('average_response_time_ms')}ms")
            
            # Validate A/B test results
            ab_results = metrics.get('ab_test_results', {})
            if ab_results.get('voice_open_rate', 0) < 0.6:
                self.warnings.append(f"Voice open rate in A/B test below expectation")
            
            if ab_results.get('statistical_significance') != "p<0.001":
                self.warnings.append(f"A/B test may not be statistically significant")
            
            print("✅ System performance validation completed")
            
        except Exception as e:
            self.errors.append(f"Failed to validate system performance: {str(e)}")
    
    def validate_policy_metadata(self):
        """Validate policy metadata"""
        try:
            with open(self.base_path / "data/policy_metadata.json", 'r') as f:
                policies = json.load(f)
            
            print(f"📋 Validating {len(policies)} policy metadata entries...")
            
            # Check we have expected number of policies
            if len(policies) != 50:
                self.warnings.append(f"Expected 50 policies, found {len(policies)}")
            
            # Validate each policy has required fields
            required_fields = ['policy_id', 'policy_type', 'provider', 'document_quality', 'language']
            for policy in policies:
                for field in required_fields:
                    if field not in policy:
                        self.errors.append(f"Policy {policy.get('policy_id', 'unknown')} missing field: {field}")
            
            # Check document quality distribution
            quality_dist = {}
            for policy in policies:
                quality = policy.get('document_quality', 'unknown')
                quality_dist[quality] = quality_dist.get(quality, 0) + 1
            
            # Should have 30% clean PDF, 50% scanned, 20% handwritten
            total = len(policies)
            clean_pct = quality_dist.get('clean_pdf', 0) / total
            scanned_pct = quality_dist.get('scanned_300dpi', 0) / total
            handwritten_pct = quality_dist.get('handwritten_annotation', 0) / total
            
            if abs(clean_pct - 0.30) > 0.05:
                self.warnings.append(f"Clean PDF distribution: expected ~30%, actual {clean_pct:.1%}")
            
            print("✅ Policy metadata validation completed")
            
        except Exception as e:
            self.errors.append(f"Failed to validate policy metadata: {str(e)}")
    
    def generate_report(self):
        """Generate validation report"""
        print("\n📋 VALIDATION REPORT")
        print("=" * 50)
        
        if self.errors:
            print("❌ ERRORS FOUND:")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print("⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        if not self.errors and not self.warnings:
            print("✅ All validations passed!")
        
        print(f"\nSUMMARY:")
        print(f"  • Errors: {len(self.errors)}")
        print(f"  • Warnings: {len(self.warnings)}")
        print(f"  • Status: {'PASSED' if not self.errors else 'FAILED'}")
        
        # Save report to file
        report = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'errors': self.errors,
            'warnings': self.warnings,
            'status': 'PASSED' if not self.errors else 'FAILED',
            'total_errors': len(self.errors),
            'total_warnings': len(self.warnings)
        }
        
        with open(self.base_path / "validation_report.json", 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Report saved to: {self.base_path / 'validation_report.json'}")

if __name__ == "__main__":
    validator = ResearchValidator()
    success = validator.validate_all()
    
    if success:
        print("\n🎉 Validation completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Validation failed with errors!")
        sys.exit(1)