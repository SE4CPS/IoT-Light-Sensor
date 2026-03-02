DevOps Workflow – IoT Light Sensor

1. Branch Strategy

    We use the production branch as the official deployment branch.

    production → Stable branch used for deployment (Render)

    main → Not used for active development

    All new work must be done in feature branches

    No direct changes should be made to production.



2. Development Workflow (Step-by-Step)

    Step 1: Start from production

    git checkout production
    git pull origin production

    This ensures your local code is up to date.


    Step 2: Create a feature branch

    git checkout -b feature/short-description

    Example:

    git checkout -b feature/add-dashboard-filter


    Step 3: Make changes and test locally

    Run the dashboard locally:  python dashboard/app.py

    Run tests:

    pytest dashboard/tests/
    pytest twin/test_twin_sim.py

    Stop server using: CTRL + C


    Step 4: Stage and commit changes

    git add .
    git status
    git commit -m "Describe your changes clearly"


    Step 5: Push feature branch

    git push -u origin feature/short-description


    Step 6: Create Pull Request (PR)

    Base branch: production

    Compare branch: feature/short-description

    Add clear description of changes

    Once PR is created:

    CI pipeline runs automatically

    Tests must pass before merge



3. CI Pipeline

    The CI workflow is located in:

    .github/workflows/tests.yml

    It runs automatically on:

    Push to production

    Pull Requests targeting production

    The pipeline:

    Installs dependencies

    Runs dashboard tests

    Runs twin tests

    This ensures that only tested code is merged.



4. Branch Protection (If Enabled)

    When branch protection is enabled for production:

    Pull Request is required before merging

    CI checks must pass

    Direct pushes to production are blocked




5. Deployment (Render)

    Render is configured to deploy from the production branch.

    After a PR is merged into production:

    DevOps team deploys to Render (manual or auto-deploy)




6. Team Communication

    After creating a PR, notify the team in Slack:

    Example message:

    Hi team, I created a PR into production for [feature name].
    CI passed successfully.
    Please review and approve.

    Slack channel: #all-iot-light-sensor

7. Summary

    Feature Branch → Pull Request → CI Check → Merge → Deploy

    This workflow ensures:

    Stability

    Code review

    Automatic testing

    Controlled deployment
