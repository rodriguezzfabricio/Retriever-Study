#!/usr/bin/env python3
"""
Group Creation Validation Monitor
QA_Engineer validation script for GROUP-CREATION-VALIDATION UTDF

This script monitors the backend database and API for group creation activity
while you manually test the frontend group creation flow.
"""

import sqlite3
import json
import time
from datetime import datetime, timedelta
import requests
import os
from pathlib import Path

class GroupCreationMonitor:
    def __init__(self):
        self.backend_url = "http://localhost:8000"
        self.db_path = "app/database.db"  # Adjust if your DB is elsewhere
        self.validation_results = []
        self.start_time = datetime.now()

    def get_current_groups_count(self):
        """Get current count of groups in database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM groups")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            print(f"Database connection issue: {e}")
            return None

    def get_recent_groups(self, minutes_ago=5):
        """Get groups created in the last N minutes."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get groups created recently
            cutoff_time = datetime.now() - timedelta(minutes=minutes_ago)
            cutoff_str = cutoff_time.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("""
                SELECT groupId, title, courseCode, ownerId, created_at, memberCount
                FROM groups
                WHERE datetime(created_at) > datetime(?)
                ORDER BY created_at DESC
            """, (cutoff_str,))

            groups = cursor.fetchall()
            conn.close()
            return groups
        except Exception as e:
            print(f"Error getting recent groups: {e}")
            return []

    def check_api_health(self):
        """Check if backend API is responding."""
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    def check_groups_endpoint(self):
        """Check if groups endpoint is accessible."""
        try:
            response = requests.get(f"{self.backend_url}/groups", timeout=5)
            return response.status_code == 200
        except:
            return False

    def validate_group_structure(self, group_data):
        """Validate that a group has the expected structure."""
        required_fields = ['groupId', 'title', 'courseCode', 'ownerId']
        validation = {
            'has_required_fields': all(field in str(group_data) for field in required_fields),
            'has_title': bool(group_data[1] if len(group_data) > 1 else False),
            'has_course_code': bool(group_data[2] if len(group_data) > 2 else False),
            'has_owner': bool(group_data[3] if len(group_data) > 3 else False),
        }
        return validation

    def start_monitoring(self):
        """Start monitoring for group creation activity."""
        print("GROUP CREATION VALIDATION MONITOR")
        print("=" * 50)
        print(f"Started monitoring at: {self.start_time.strftime('%H:%M:%S')}")
        print(f"Backend URL: {self.backend_url}")
        print(f"Database: {self.db_path}")
        print()

        # Initial health checks
        print("HEALTH CHECKS:")
        api_healthy = self.check_api_health()
        groups_endpoint_ok = self.check_groups_endpoint()
        initial_count = self.get_current_groups_count()

        print(f"Backend API: {'HEALTHY' if api_healthy else 'DOWN'}")
        print(f"Groups Endpoint: {'ACCESSIBLE' if groups_endpoint_ok else 'ERROR'}")
        print(f"Database: {'CONNECTED' if initial_count is not None else 'ERROR'}")
        print(f"Current Groups Count: {initial_count}")
        print()

        if not all([api_healthy, groups_endpoint_ok, initial_count is not None]):
            print("CRITICAL: Backend not ready for testing!")
            return False

        print("READY FOR MANUAL TESTING!")
        print("Please proceed with:")
        print("1. Open frontend (http://localhost:3000)")
        print("2. Log in with your Google account")
        print("3. Click 'CREATE GROUP' button")
        print("4. Fill out and submit the form")
        print()
        print("Monitoring for changes... (Press Ctrl+C to stop)")
        print()

        return self.monitor_loop(initial_count)

    def monitor_loop(self, initial_count):
        """Main monitoring loop."""
        last_count = initial_count
        validation_results = []

        try:
            while True:
                time.sleep(2)  # Check every 2 seconds

                current_count = self.get_current_groups_count()
                if current_count is None:
                    continue

                # Check for new groups
                if current_count > last_count:
                    new_groups = self.get_recent_groups(minutes_ago=1)

                    for group in new_groups:
                        result = self.validate_new_group(group)
                        validation_results.append(result)
                        self.print_validation_result(result)

                    last_count = current_count

                    # If we detected group creation, wait a bit more then generate report
                    print("\nWaiting 10 seconds for any additional changes...")
                    time.sleep(10)
                    self.generate_final_report(validation_results)
                    return True

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")
            if validation_results:
                self.generate_final_report(validation_results)
            else:
                print("No group creation detected during monitoring session")
            return len(validation_results) > 0

    def validate_new_group(self, group_data):
        """Validate a newly created group."""
        timestamp = datetime.now()
        group_id, title, course_code, owner_id, created_at, member_count = group_data

        validation = {
            'timestamp': timestamp,
            'group_id': group_id,
            'title': title,
            'course_code': course_code,
            'owner_id': owner_id,
            'created_at': created_at,
            'member_count': member_count,
            'validations': {
                'has_valid_id': bool(group_id),
                'has_title': bool(title and len(title.strip()) > 0),
                'has_course_code': bool(course_code and len(course_code.strip()) > 0),
                'has_owner': bool(owner_id),
                'correct_initial_member_count': member_count == 1,
                'recent_creation': True  # Since we're checking recent groups
            }
        }

        # Test API accessibility of new group
        try:
            response = requests.get(f"{self.backend_url}/groups/{group_id}", timeout=5)
            validation['api_accessible'] = response.status_code == 200
            if response.status_code == 200:
                group_details = response.json()
                validation['api_data'] = group_details
        except:
            validation['api_accessible'] = False
            validation['api_data'] = None

        return validation

    def print_validation_result(self, result):
        """Print validation result in real-time."""
        print(f"NEW GROUP DETECTED!")
        print(f"Time: {result['timestamp'].strftime('%H:%M:%S')}")
        print(f"Group ID: {result['group_id']}")
        print(f"Title: {result['title']}")
        print(f"Course: {result['course_code']}")
        print(f"Owner: {result['owner_id']}")
        print(f"Members: {result['member_count']}")
        print()

        print("VALIDATION CHECKS:")
        validations = result['validations']
        for check, passed in validations.items():
            status = "PASS" if passed else "FAIL"
            print(f"  {status}: {check.replace('_', ' ').title()}")

        api_status = "PASS" if result.get('api_accessible') else "FAIL"
        print(f"  {api_status}: API Accessible")
        print()

    def generate_final_report(self, results):
        """Generate final validation report."""
        print("\n" + "="*60)
        print("GROUP CREATION VALIDATION REPORT")
        print("="*60)

        if not results:
            print("NO GROUP CREATION DETECTED")
            print("\nPossible issues:")
            print("- Frontend form not submitting")
            print("- Authentication not working")
            print("- API endpoint not receiving requests")
            print("- Database not being updated")
            return

        for i, result in enumerate(results, 1):
            print(f"\nGROUP {i} VALIDATION:")
            print(f"Title: {result['title']}")
            print(f"Course: {result['course_code']}")
            print(f"Created: {result['created_at']}")

            # Overall validation score
            validations = result['validations']
            passed_checks = sum(1 for v in validations.values() if v)
            total_checks = len(validations)
            api_check = 1 if result.get('api_accessible') else 0

            overall_score = (passed_checks + api_check) / (total_checks + 1) * 100

            print(f"Validation Score: {overall_score:.1f}% ({passed_checks + api_check}/{total_checks + 1})")

            if overall_score >= 90:
                print("STATUS: EXCELLENT - Group creation working perfectly!")
            elif overall_score >= 70:
                print("STATUS: GOOD - Group creation mostly working, minor issues")
            else:
                print("STATUS: ISSUES - Group creation has problems")

        # UTDF Recommendations
        print(f"\nUTDF RECOMMENDATION:")
        if all(self.calculate_group_score(r) >= 90 for r in results):
            print("PROCEED TO FE-01 (Full Profile Editing)")
            print("Group creation flow is working excellently!")
        else:
            print("RECOMMEND FIXES before FE-01")
            print("Group creation has issues that should be addressed")

        print("\n" + "="*60)

    def calculate_group_score(self, result):
        """Calculate overall score for a group creation."""
        validations = result['validations']
        passed_checks = sum(1 for v in validations.values() if v)
        total_checks = len(validations)
        api_check = 1 if result.get('api_accessible') else 0
        return (passed_checks + api_check) / (total_checks + 1) * 100


if __name__ == "__main__":
    monitor = GroupCreationMonitor()

    print("GROUP CREATION VALIDATION SETUP")
    print("This script will monitor your backend while you manually test group creation")
    print()

    # Check if we're in the right directory
    if not os.path.exists("app"):
        print("ERROR: Please run this script from the backend directory:")
        print("   cd /path/to/retriever-study/backend")
        print("   python group_creation_monitor.py")
        exit(1)

    success = monitor.start_monitoring()

    if success:
        print("\nGroup creation validation completed successfully!")
    else:
        print("\nGroup creation validation completed with issues")