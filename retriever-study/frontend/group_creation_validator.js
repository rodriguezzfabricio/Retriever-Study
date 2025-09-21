#!/usr/bin/env node
/**
 * Frontend Group Creation Flow Validator
 * QA_Engineer validation script for GROUP-CREATION-VALIDATION UTDF
 *
 * This script validates the frontend group creation flow components and API calls.
 */

const fs = require('fs');
const path = require('path');

class FrontendGroupValidator {
    constructor() {
        this.srcPath = path.join(__dirname, 'src');
        this.validationResults = [];
    }

    checkFileExists(filePath) {
        try {
            return fs.existsSync(filePath);
        } catch (error) {
            return false;
        }
    }

    readFileContent(filePath) {
        try {
            return fs.readFileSync(filePath, 'utf8');
        } catch (error) {
            return null;
        }
    }

    validateCreateGroupModal() {
        const modalPath = path.join(this.srcPath, 'components', 'CreateGroupModal.js');
        const modalExists = this.checkFileExists(modalPath);

        if (!modalExists) {
            return {
                component: 'CreateGroupModal',
                exists: false,
                validations: {}
            };
        }

        const content = this.readFileContent(modalPath);
        if (!content) {
            return {
                component: 'CreateGroupModal',
                exists: false,
                validations: {}
            };
        }

        const validations = {
            has_form_fields: content.includes('courseCode') && content.includes('title') && content.includes('description'),
            has_submit_handler: content.includes('onSubmit') || content.includes('handleSubmit'),
            has_api_call: content.includes('createGroup') || content.includes('fetch'),
            has_auth_context: content.includes('useAuth') || content.includes('AuthContext'),
            has_error_handling: content.includes('catch') || content.includes('error'),
            has_loading_state: content.includes('loading') || content.includes('Loading'),
            has_form_validation: content.includes('required') || content.includes('validate')
        };

        return {
            component: 'CreateGroupModal',
            exists: true,
            validations,
            file_path: modalPath
        };
    }

    validateApiService() {
        const apiPath = path.join(this.srcPath, 'services', 'api.js');
        const apiExists = this.checkFileExists(apiPath);

        if (!apiExists) {
            return {
                component: 'API Service',
                exists: false,
                validations: {}
            };
        }

        const content = this.readFileContent(apiPath);
        if (!content) {
            return {
                component: 'API Service',
                exists: false,
                validations: {}
            };
        }

        const validations = {
            has_create_group_function: content.includes('createGroup'),
            has_auth_headers: content.includes('Authorization') || content.includes('Bearer'),
            has_error_handling: content.includes('ApiError') || content.includes('throw'),
            has_proper_endpoint: content.includes('/groups'),
            has_post_method: content.includes('POST') || content.includes('method'),
            exports_create_group: content.includes('export') && content.includes('createGroup')
        };

        return {
            component: 'API Service',
            exists: true,
            validations,
            file_path: apiPath
        };
    }

    validateGroupsPage() {
        const groupsPagePath = path.join(this.srcPath, 'pages', 'GroupsList.js');
        const groupsPageExists = this.checkFileExists(groupsPagePath);

        if (!groupsPageExists) {
            return {
                component: 'GroupsList Page',
                exists: false,
                validations: {}
            };
        }

        const content = this.readFileContent(groupsPagePath);
        if (!content) {
            return {
                component: 'GroupsList Page',
                exists: false,
                validations: {}
            };
        }

        const validations = {
            has_create_button: content.includes('CREATE') || content.includes('create'),
            has_modal_integration: content.includes('CreateGroupModal') || content.includes('Modal'),
            has_groups_listing: content.includes('groups') && content.includes('map'),
            has_auth_check: content.includes('useAuth') || content.includes('isAuthenticated'),
            has_loading_state: content.includes('loading') || content.includes('Loading')
        };

        return {
            component: 'GroupsList Page',
            exists: true,
            validations,
            file_path: groupsPagePath
        };
    }

    validateAuthContext() {
        const authPath = path.join(this.srcPath, 'context', 'AuthContext.js');
        const authExists = this.checkFileExists(authPath);

        if (!authExists) {
            return {
                component: 'AuthContext',
                exists: false,
                validations: {}
            };
        }

        const content = this.readFileContent(authPath);
        if (!content) {
            return {
                component: 'AuthContext',
                exists: false,
                validations: {}
            };
        }

        const validations = {
            provides_user: content.includes('user') && content.includes('Provider'),
            provides_token: content.includes('token'),
            provides_auth_state: content.includes('isAuthenticated'),
            has_login_function: content.includes('login'),
            exports_use_auth: content.includes('useAuth') && content.includes('export')
        };

        return {
            component: 'AuthContext',
            exists: true,
            validations,
            file_path: authPath
        };
    }

    validateProtectedRoute() {
        const protectedPath = path.join(this.srcPath, 'components', 'ProtectedRoute.js');
        const protectedExists = this.checkFileExists(protectedPath);

        const validations = {
            component_exists: protectedExists
        };

        if (protectedExists) {
            const content = this.readFileContent(protectedPath);
            validations.checks_auth = content.includes('isAuthenticated') || content.includes('useAuth');
            validations.redirects_unauth = content.includes('redirect') || content.includes('Navigate');
        }

        return {
            component: 'ProtectedRoute',
            exists: protectedExists,
            validations,
            file_path: protectedExists ? protectedPath : null
        };
    }

    runValidation() {
        console.log('FRONTEND GROUP CREATION VALIDATION');
        console.log('=' .repeat(50));
        console.log('Checking frontend components and integration...\n');

        const components = [
            this.validateCreateGroupModal(),
            this.validateApiService(),
            this.validateGroupsPage(),
            this.validateAuthContext(),
            this.validateProtectedRoute()
        ];

        let overallScore = 0;
        let totalChecks = 0;

        components.forEach(component => {
            console.log(`${component.component}:`);
            console.log(`  File exists: ${component.exists ? 'PASS' : 'FAIL'}`);

            if (component.exists && component.validations) {
                const checks = Object.entries(component.validations);
                const passedChecks = checks.filter(([key, value]) => value).length;
                const componentScore = (passedChecks / checks.length) * 100;

                checks.forEach(([check, passed]) => {
                    const status = passed ? 'PASS' : 'FAIL';
                    console.log(`  ${check.replace(/_/g, ' ')}: ${status}`);
                });

                console.log(`  Component Score: ${componentScore.toFixed(1)}%\n`);
                overallScore += componentScore;
                totalChecks += 1;
            } else {
                console.log('  Cannot validate - file missing\n');
            }
        });

        const finalScore = totalChecks > 0 ? overallScore / totalChecks : 0;

        console.log('=' .repeat(50));
        console.log('FRONTEND VALIDATION SUMMARY');
        console.log('=' .repeat(50));
        console.log(`Overall Frontend Score: ${finalScore.toFixed(1)}%`);

        if (finalScore >= 90) {
            console.log('STATUS: EXCELLENT - Frontend ready for testing');
        } else if (finalScore >= 70) {
            console.log('STATUS: GOOD - Frontend mostly ready, minor issues');
        } else {
            console.log('STATUS: ISSUES - Frontend has significant problems');
        }

        console.log('\nCRITICAL COMPONENTS STATUS:');
        const criticalComponents = ['CreateGroupModal', 'API Service', 'AuthContext'];
        const criticalResults = components.filter(c => criticalComponents.includes(c.component));

        criticalResults.forEach(component => {
            const status = component.exists ? 'READY' : 'MISSING';
            console.log(`  ${component.component}: ${status}`);
        });

        return {
            overallScore: finalScore,
            components,
            ready: finalScore >= 70
        };
    }
}

// Manual Testing Instructions Generator
function generateTestingInstructions() {
    console.log('\n' + '=' .repeat(60));
    console.log('MANUAL TESTING INSTRUCTIONS');
    console.log('=' .repeat(60));
    console.log('Follow these steps to test group creation flow:\n');

    console.log('STEP 1: Start Applications');
    console.log('  - Ensure backend is running on http://localhost:8000');
    console.log('  - Ensure frontend is running on http://localhost:3000');
    console.log('  - Run backend monitor: python group_creation_monitor.py\n');

    console.log('STEP 2: Authentication');
    console.log('  - Navigate to http://localhost:3000');
    console.log('  - Click "LOG IN" button');
    console.log('  - Complete Google OAuth authentication');
    console.log('  - Verify you see "HELLO, [Name]" in header\n');

    console.log('STEP 3: Group Creation Test');
    console.log('  - Navigate to /groups page');
    console.log('  - Click "CREATE GROUP" button');
    console.log('  - Verify modal opens with form fields');
    console.log('  - Fill out form:');
    console.log('    * Course Code: "CS101"');
    console.log('    * Title: "Test Study Group"');
    console.log('    * Description: "Testing group creation"');
    console.log('    * Set location, max members, etc.');
    console.log('  - Click Submit/Create button\n');

    console.log('STEP 4: Verification');
    console.log('  - Check if redirected to group detail page');
    console.log('  - Verify group appears in /groups listing');
    console.log('  - Verify you can access group chat');
    console.log('  - Check backend monitor output for validation results\n');

    console.log('EXPECTED RESULTS:');
    console.log('  - Group created successfully in database');
    console.log('  - API returns proper group data');
    console.log('  - Frontend displays new group');
    console.log('  - User can immediately access group features');
}

if (require.main === module) {
    console.log('GROUP CREATION FRONTEND VALIDATION');
    console.log('This script validates frontend components for group creation flow\n');

    const validator = new FrontendGroupValidator();
    const results = validator.runValidation();

    generateTestingInstructions();

    console.log('\nREADY FOR MANUAL TESTING:', results.ready ? 'YES' : 'NO');

    if (!results.ready) {
        console.log('RECOMMENDATION: Fix frontend issues before manual testing');
    } else {
        console.log('RECOMMENDATION: Proceed with manual testing');
    }
}

module.exports = FrontendGroupValidator;