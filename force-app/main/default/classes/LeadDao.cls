/**
 * @description  DAO for Lead queries, optimized for bulk operations.
 * @version      1.1.0
 * @author       ProContacto
 */
public with sharing class LeadDao {

    /**
     * @description Retrieve Lead by internal ids
     * @param ids List of lead ids
     * @return List<Lead> List of leads
     */
    public static List<Lead> getLeadsFromIds(List<String> ids) {
        return [SELECT Id, Name
            FROM Lead
            WHERE Id = :ids
        ];
    }

    /**
     * @description Finds existing leads that match any of the provided criteria sets.
     * @param firstNames Set of First Names to search.
     * @param lastNames Set of Last Names to search.
     * @param phones Set of Phones to search.
     * @param streets Set of Streets to search.
     * @param cities Set of Cities to search.
     * @return List<Lead> List of all existing leads that match criteria.
     */
    public static List<Lead> findPotentialDuplicatesBulk(
        Set<String> firstNames, Set<String> lastNames,
        Set<String> phones,
        Set<String> streets, Set<String> cities
    ) {
        // Construimos una query dinámica o con ORs para traer todo en 1 o pocas llamadas.
        // Por simplicidad y evitar 'Query too complex', a veces es mejor separarlo en 3 queries simples
        // ya que los Governor Limits permiten hasta 100 queries, pero pocas filas.

        List<Lead> results = new List<Lead>();

        if (!firstNames.isEmpty() && !lastNames.isEmpty()) {
            results.addAll([
                SELECT Id, FirstName, LastName, Phone, Street, City
                FROM Lead
                WHERE FirstName IN :firstNames AND LastName IN :lastNames AND IsConverted = false
            ]);
        }

        if (!phones.isEmpty()) {
            results.addAll([
                SELECT Id, FirstName, LastName, Phone, Street, City
                FROM Lead
                WHERE Phone IN :phones AND IsConverted = false
            ]);
        }

        if (!streets.isEmpty() && !cities.isEmpty()) {
            results.addAll([
                SELECT Id, FirstName, LastName, Phone, Street, City
                FROM Lead
                WHERE Street IN :streets AND City IN :cities AND IsConverted = false
            ]);
        }

        return results;
    }
}