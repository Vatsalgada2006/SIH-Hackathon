    # Define a side effect function for db_session.execute
    def execute_side_effect(query):
        query_str = str(query)
        print(f"Executing query: {query_str}")
        if "SELECT road_segments.id" in query_str and "ORDER BY ST_Distance" in query_str:
            # Mock for the nearest segment query
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = segment.id
            return mock_result
        elif "SELECT incidents.id" in query_str and "WHERE incidents.id =" in query_str:
            # Mock for getting the incident (refresh and get_incident)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_incident
            print(f"Returning mock_incident: {mock_incident}")
            return mock_result
        elif "SELECT audit_logs.id" in query_str:
            # Mock for getting the audit log (refresh in create_audit_log)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_audit_log
            return mock_result
        else:
            # For any other query (including updates), return a mock that returns None for scalar_one_or_none
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            return mock_result

    db_session.execute.side_effect = execute_side_effect
    print(f"Side effect set: {db_session.execute.side_effect}")
