.PHONY: test lint

# Runs inside the CARE backend container, where care_maternal is installed in editable mode.
TEST_LABELS = care_maternal.tests.test_schedule care_maternal.tests.test_services_api \
	care_maternal.tests.test_referrals care_maternal.tests.test_tags \
	care_maternal.tests.test_booking care_maternal.tests.test_no_show

test:
	python manage.py test $(TEST_LABELS)

lint:
	ruff check src
